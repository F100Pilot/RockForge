// Rocksmith-style 3D note highway for the Partitura page ("Pista 3D").
//
// A classic script (like app.js) that exposes window.Highway3D. three.js is
// vendored under /vendor/three/ and imported only when the highway is first
// shown, so the page pays nothing for it until then and it works offline.
//
// It knows nothing about sync: app.js hands it the notes already mapped to the
// DISPLAY clock the score draws them on (warp(previewScale(t)), so pending
// tempo/anchor edits show here live) and a getNow() callback that answers the
// playhead in that same clock. Only the notes inside the visible window are
// turned into meshes, and geometries/materials are shared, so a song with
// thousands of notes costs the same as a short one.
(() => {
  "use strict";

  const THREE_URL = "/vendor/three/three.module.js";
  let THREE = null;
  let loading = null;

  // --- Look (the approved sketch) ---------------------------------------------------------------
  // string 0 = low E: red and drawn on top, as in Rocksmith.
  const STRING_COLORS = [0xe8363a, 0xf5d130, 0x2f8ff0, 0xf7862a, 0x3fbf4a, 0xa955e0];
  const STANDARD = [40, 45, 50, 55, 59, 64];
  const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
  const FRETS = 24;
  const GAP = 0.44;
  const SPEED = 9; // highway units per second of song
  const AHEAD = 5.2; // seconds of notes in view
  const FAR = SPEED * AHEAD;
  const NECK_NEAR = 1.7;
  const NECK_FAR = -0.7;
  const NUT_W = 0.55;
  const HOLD_MIN = 0.32; // a struck note stays on the string at least this long
  // A note comes tilted NOTE_ROLL_DEG (its right side up) and, over its last NOTE_ROLL_S before
  // the strings, turns clockwise at a constant rate to lie level as it strikes (30°, 3 s,
  // constant). A chord turns as one piece, around its frame's centre. An open string (the bar
  // across the hand's frets) always lies level, and so does a chord with one.
  const NOTE_ROLL_DEG = 30;
  const NOTE_ROLL_S = 3;
  const SLIDE_BLEND = 0.25; // share of a slide's trail each curved end takes…
  const SLIDE_BLEND_MAX = 0.6; // …at most this long on the highway (a small curve)
  const comesLevel = (n) => n.fret === 0 || (n.chord && n.chord.members.some((m) => m.fret === 0));
  const noteRoll = (remaining) => remaining <= 0 ? 0
    : (NOTE_ROLL_DEG * Math.PI / 180) * Math.min(1, remaining / NOTE_ROLL_S);
  const FADE = 0.25;
  const CHORD_EPS = 0.005;
  const ANCHOR_AHEAD = 1.6; // the hand window covers the notes this far ahead
  const INLAYS = [3, 5, 7, 9, 12, 15, 17, 19, 21, 24];
  const stringY = (s) => 0.55 + (5 - s) * GAP;
  const fretX = (f) => f - 0.5; // centre of the space behind fret wire f
  const pegX = (s) => -1.25 - (5 - s) * 0.34; // staggered like a 6-in-line head
  const hex = (c) => `#${c.toString(16).padStart(6, "0")}`;

  // Rocksmith's notehead symbols (its "Notehead and tail guide"), drawn on a 128 px canvas:
  // hammer-on ▼ and pull-off ▲ (on the note's face), and above the note palm mute (a bow tie),
  // harmonic (a ring with a dot), pinch harmonic (an eye), tap (a wide V), slap (a block with a
  // notch), pop (a block with a peak) and a bend's strength as stacked chevrons.
  const ring = (ctx, radius) => { ctx.moveTo(64 + radius, 64); ctx.arc(64, 64, radius, 0, 2 * Math.PI); };
  const ICONS = {
    hammerOn: (ctx) => { ctx.moveTo(24, 34); ctx.lineTo(104, 34); ctx.lineTo(64, 100); ctx.closePath(); },
    pullOff: (ctx) => { ctx.moveTo(24, 96); ctx.lineTo(104, 96); ctx.lineTo(64, 30); ctx.closePath(); },
    harmonic: (ctx) => { ring(ctx, 42); ring(ctx, 30); ring(ctx, 12); },
    pinchHarmonic: (ctx) => {
      ctx.moveTo(10, 64); ctx.quadraticCurveTo(64, 6, 118, 64); ctx.quadraticCurveTo(64, 122, 10, 64); ctx.closePath();
      ring(ctx, 22); ring(ctx, 11);
    },
    tap: (ctx) => { ctx.moveTo(14, 36); ctx.lineTo(64, 100); ctx.lineTo(114, 36); ctx.lineTo(90, 36); ctx.lineTo(64, 70); ctx.lineTo(38, 36); ctx.closePath(); },
    slap: (ctx) => { ctx.moveTo(10, 44); ctx.lineTo(64, 74); ctx.lineTo(118, 44); ctx.lineTo(118, 96); ctx.lineTo(10, 96); ctx.closePath(); },
    pluck: (ctx) => { ctx.moveTo(10, 72); ctx.lineTo(64, 36); ctx.lineTo(118, 72); ctx.lineTo(118, 96); ctx.lineTo(10, 96); ctx.closePath(); },
  };
  // `count` chevrons stacked upwards, 16 px thick: a bend of a half step, a whole step, more.
  const chevrons = (count) => (ctx) => {
    const start = 104 - (3 - count) * 14; // centre the stack
    for (let i = 0; i < count; i += 1) {
      const arms = start - i * 28, tip = arms - 30;
      ctx.moveTo(24, arms); ctx.lineTo(64, tip); ctx.lineTo(104, arms);
      ctx.lineTo(104, arms + 16); ctx.lineTo(64, tip + 16); ctx.lineTo(24, arms + 16);
      ctx.closePath();
    }
  };
  // Symbols above the note, in this order (side by side when there are several).
  const ABOVE = ["tap", "harmonic", "pinchHarmonic", "slap", "pluck"]; // palm mute: a cross in the note
  const LEGATO = ["hammerOn", "pullOff"];
  const FRET_RAMP = 2; // seconds before its note in which a fret number of the neck lights up
  const AMBER = 0xffb43a;
  // A bend in teal: its trail rises along the bend's curve and, on the string, the note rises as
  // it is bent, into a frame at the height it has to reach. BEND_Y per semitone, so a full step
  // rises one string gap (as far as a finger pushes the string), at most BEND_MAX semitones.
  const TEAL = 0x3ddcc4;
  const BEND_Y = GAP / 2;
  const BEND_MAX = 3;

  let stage = null; // renderer, scene, camera and everything static
  let song = null; // the current notes and their live meshes
  let getNow = () => ({ t: 0, playing: false });
  // The camera turns around a point between the strings and the notes about to arrive: up to
  // YAW_MAX degrees to either side, from level with the highway (0) to straight above it (90),
  // nearer or further. The default is the view from before the camera could turn.
  const CAMERA_DEFAULT = { yaw: 0, pitch: 15, dist: 15 };
  const YAW_MAX = 120;
  const PITCH_MAX = 90;
  const DIST_MIN = 6;
  const DIST_MAX = 40;
  const PIVOT_Y = 2;
  const PIVOT_Z = -4;
  let options = { numbers: false, ...CAMERA_DEFAULT };
  let onCamera = null; // told when the camera is turned on the canvas
  let raf = 0;
  let lastNow = null;
  let lastFrame = 0;

  function load() {
    if (THREE) return Promise.resolve(THREE);
    if (!loading) {
      loading = import(THREE_URL).then(
        (module) => { THREE = module; return THREE; },
        (error) => { loading = null; throw error; },
      );
    }
    return loading;
  }

  // --- Shared resources ---------------------------------------------------------------------------
  let res = null;
  function canvasTexture(width, height, draw) {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    draw(canvas.getContext("2d"), width, height);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = 4;
    return texture;
  }
  function textTexture(text, color = "#ffffff", { size = 96, outline = 14, width = 128 } = {}) {
    return canvasTexture(width, 128, (ctx, w, h) => {
      ctx.font = `700 ${size}px "Barlow Condensed", "Arial Narrow", system-ui, sans-serif`;
      const fit = (w - 16) / ctx.measureText(text).width;
      if (fit < 1) ctx.font = `700 ${Math.floor(size * fit)}px "Barlow Condensed", "Arial Narrow", system-ui, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.lineJoin = "round";
      ctx.lineWidth = outline;
      ctx.strokeStyle = "rgba(0,0,0,0.9)";
      ctx.strokeText(text, w / 2, h / 2 + 4);
      ctx.fillStyle = color;
      ctx.fillText(text, w / 2, h / 2 + 4);
    });
  }
  // A notehead symbol: white (or `color`) with a dark outline, filled even-odd (rings, the eye).
  function iconTexture(key) {
    const [name, color] = key.split("|");
    return canvasTexture(128, 128, (ctx) => {
      ctx.beginPath();
      (name.startsWith("bend") ? chevrons(Number(name.slice(4))) : ICONS[name])(ctx);
      ctx.lineJoin = "round";
      ctx.lineWidth = 8;
      ctx.strokeStyle = "#000000";
      ctx.stroke();
      ctx.fillStyle = color || "#ffffff";
      ctx.fill("evenodd");
    });
  }
  function roundedRect(w, h, r) {
    const s = new THREE.Shape();
    const x = -w / 2, y = -h / 2;
    s.moveTo(x + r, y);
    s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r);
    s.lineTo(x + w, y + h - r); s.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r);
    s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
    return s;
  }
  // A note is see-through: a glowing outline in the string's colour around a faint fill
  // (Rocksmith's look), not a solid gem.
  function outlineGeometries(w, h) {
    const r = Math.min(0.12, h / 2 - 0.01), t = 0.055;
    const ring = roundedRect(w, h, r);
    ring.holes.push(roundedRect(w - 2 * t, h - 2 * t, Math.max(0.02, r - t)));
    const halo = roundedRect(w + 0.14, h + 0.14, r + 0.07);
    halo.holes.push(roundedRect(w - 0.02, h - 0.02, r));
    return {
      ring: new THREE.ShapeGeometry(ring, 8),
      halo: new THREE.ShapeGeometry(halo, 8),
      fill: new THREE.ShapeGeometry(roundedRect(w - t, h - t, Math.max(0.02, r - t / 2)), 8),
    };
  }
  function addOutline(group, shapes, mats) {
    const fill = new THREE.Mesh(shapes.fill, mats.fill); fill.position.z = -0.01;
    const halo = new THREE.Mesh(shapes.halo, mats.halo); halo.position.z = -0.005;
    group.add(fill, halo, new THREE.Mesh(shapes.ring, mats.ring));
  }
  // Palm mute: a translucent cross from corner to corner inside the note's outline, in the string's
  // colour. Two bars, each clipped to the inner rectangle.
  function crossGeometry(key) {
    const [width, height] = key.split(":").map(Number);
    const a = width / 2 - 0.05; // inside the ring
    const b = height / 2 - 0.05;
    const slope = b / a;
    const dx = (0.03 * Math.hypot(1, slope)) / slope; // half a bar 0.06 wide, measured along x
    const bar = (sign) => {
      const shape = new THREE.Shape();
      shape.moveTo(-a, -sign * b);
      shape.lineTo(-a + dx, -sign * b);
      shape.lineTo(a, sign * (b - dx * slope));
      shape.lineTo(a, sign * b);
      shape.lineTo(a - dx, sign * b);
      shape.lineTo(-a, -sign * (b - dx * slope));
      shape.closePath();
      return shape;
    };
    return new THREE.ShapeGeometry([bar(1), bar(-1)]);
  }
  function addPalmMute(group, n, width, material) {
    if (!n.techniques.includes("palmMute") || n.techniques.includes("mute")) return;
    const size = n.fret === 0 ? `${(Math.round((width - 0.15) * 4) / 4).toFixed(2)}:0.26` : "0.82:0.4";
    const cross = new THREE.Mesh(resources().cross(size), material);
    cross.position.z = 0.002;
    group.add(cross);
  }
  function outlineMats(color, clip, lit = false) {
    return {
      ring: new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 1, depthWrite: false, clippingPlanes: clip }),
      halo: new THREE.MeshBasicMaterial({ color, transparent: true, opacity: lit ? 0.55 : 0.3, blending: THREE.AdditiveBlending, depthWrite: false, clippingPlanes: clip }),
      fill: new THREE.MeshBasicMaterial({ color, transparent: true, opacity: lit ? 0.3 : 0.12, depthWrite: false, clippingPlanes: clip }),
    };
  }

  function resources() {
    if (res) return res;
    const clip = [new THREE.Plane(new THREE.Vector3(0, 0, -1), 0.02)];
    const cache = (fn) => { const m = new Map(); return (k) => { if (!m.has(k)) m.set(k, fn(k)); return m.get(k); }; };
    res = {
      clip,
      noteOutline: outlineGeometries(0.82, 0.4),
      openOutline: cache((w) => outlineGeometries(w, 0.26)),
      outlineMats: STRING_COLORS.map((c) => outlineMats(c, clip)),
      mutedOutlineMats: outlineMats(0x8a90a0, clip),
      cross: cache(crossGeometry),
      crossMats: STRING_COLORS.map((c) => new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: 0.45, depthWrite: false, clippingPlanes: clip })),
      square: new THREE.PlaneGeometry(1, 1),
      stemMats: STRING_COLORS.map((c) => new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: 0.5, depthWrite: false, clippingPlanes: clip })),
      bendTrailMat: new THREE.MeshStandardMaterial({ color: TEAL, emissive: TEAL, emissiveIntensity: 0.75, transparent: true, opacity: 0.7, depthWrite: false, side: THREE.DoubleSide, clippingPlanes: clip }),
      // The frame a bent note rises into on the string: the height its bend reaches.
      bendTargetTex: canvasTexture(256, 128, (ctx) => {
        ctx.strokeStyle = "#3ddcc4";
        ctx.shadowColor = "#3ddcc4";
        ctx.shadowBlur = 12;
        ctx.lineWidth = 8;
        ctx.setLineDash([22, 12]);
        ctx.beginPath(); ctx.roundRect(10, 10, 236, 108, 20); ctx.stroke();
      }),
      trailMats: STRING_COLORS.map((c) => new THREE.MeshStandardMaterial({ color: c, emissive: c, emissiveIntensity: 0.6, transparent: true, opacity: 0.55, depthWrite: false, side: THREE.DoubleSide, clippingPlanes: clip })),
      frameMat: new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.6, depthWrite: false, clippingPlanes: clip }),
      barMat: new THREE.MeshBasicMaterial({ color: 0xaab6e0, transparent: true, opacity: 0.85, depthWrite: false }),
      beatMat: new THREE.MeshBasicMaterial({ color: 0x4a5a85, transparent: true, opacity: 0.6, depthWrite: false }),
      faceMat: cache((text) => new THREE.MeshBasicMaterial({ map: textTexture(text, "#ffffff", { size: 92, outline: 16 }), transparent: true, depthWrite: false, clippingPlanes: clip })),
      markMat: cache((text) => new THREE.MeshBasicMaterial({ map: textTexture(text, "#ffffff", { width: 256, size: 84 }), transparent: true, depthWrite: false, clippingPlanes: clip })),
      iconMat: cache((key) => new THREE.MeshBasicMaterial({ map: iconTexture(key), transparent: true, depthWrite: false, clippingPlanes: clip })),
      // Accent: a glowing double frame around the note (Rocksmith's).
      accentMat: new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false, clippingPlanes: clip, map: canvasTexture(256, 128, (ctx) => {
        ctx.strokeStyle = "#ffffff";
        ctx.shadowColor = "#ffd54f";
        ctx.shadowBlur = 10;
        ctx.lineWidth = 7;
        ctx.beginPath(); ctx.roundRect(8, 8, 240, 112, 18); ctx.stroke();
        ctx.lineWidth = 4;
        ctx.beginPath(); ctx.roundRect(22, 22, 212, 84, 12); ctx.stroke();
      }) }),
      // Amber halo behind a lit fret number of the neck.
      fretGlowTex: cache((text) => canvasTexture(128, 128, (ctx, w, h) => {
        ctx.font = `700 96px "Barlow Condensed", "Arial Narrow", system-ui, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.shadowColor = "#ff9d00";
        ctx.shadowBlur = 30;
        ctx.fillStyle = "#ffb43a";
        for (let pass = 0; pass < 4; pass += 1) ctx.fillText(text, w / 2, h / 2 + 4); // stacked: a stronger halo
      })),
      labelMat: cache((key) => {
        const [color, text] = key.split("|");
        return new THREE.MeshBasicMaterial({ map: textTexture(text, color, { width: 512, size: 80 }), transparent: true, depthWrite: false });
      }),
      glowTex: canvasTexture(128, 128, (ctx, w, h) => {
        const g = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w / 2);
        g.addColorStop(0, "rgba(255,255,255,1)");
        g.addColorStop(0.25, "rgba(255,255,255,0.75)");
        g.addColorStop(1, "rgba(255,255,255,0)");
        ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
      }),
      lineGlowTex: canvasTexture(8, 64, (ctx, w, h) => {
        const g = ctx.createLinearGradient(0, 0, 0, h);
        g.addColorStop(0, "rgba(255,255,255,0)");
        g.addColorStop(0.5, "rgba(255,255,255,1)");
        g.addColorStop(1, "rgba(255,255,255,0)");
        ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
      }),
      woodTex: canvasTexture(1024, 128, (ctx, w, h) => {
        ctx.fillStyle = "#2a170e"; ctx.fillRect(0, 0, w, h);
        let seed = 7;
        const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
        for (let i = 0; i < 140; i += 1) {
          ctx.strokeStyle = `rgba(${60 + rnd() * 40},${30 + rnd() * 20},${16 + rnd() * 10},${0.25 + rnd() * 0.3})`;
          ctx.lineWidth = 1 + rnd() * 2;
          const y = rnd() * h;
          ctx.beginPath(); ctx.moveTo(0, y);
          ctx.bezierCurveTo(w * 0.3, y + (rnd() - 0.5) * 12, w * 0.7, y + (rnd() - 0.5) * 12, w, y + (rnd() - 0.5) * 8);
          ctx.stroke();
        }
      }),
    };
    return res;
  }

  // --- Stage --------------------------------------------------------------------------------------
  function clampCamera(o) {
    const clamp = (v, lo, hi, d) => (Number.isFinite(v) ? Math.min(hi, Math.max(lo, v)) : d);
    return {
      yaw: clamp(o.yaw, -YAW_MAX, YAW_MAX, CAMERA_DEFAULT.yaw),
      pitch: clamp(o.pitch, 0, PITCH_MAX, CAMERA_DEFAULT.pitch),
      dist: clamp(o.dist, DIST_MIN, DIST_MAX, CAMERA_DEFAULT.dist),
    };
  }
  function turnCamera(next) {
    options = { ...options, ...clampCamera({ ...options, ...next }) };
    if (onCamera) onCamera({ yaw: options.yaw, pitch: options.pitch, dist: options.dist });
  }
  // Drag to turn (sideways = around, up/down = from above or below), the wheel for the
  // distance, a double click for the default view. The wheel only zooms once the canvas
  // has been clicked (it holds the focus until a click elsewhere or Esc): scrolling the
  // page over the highway used to zoom it instead.
  function wireCamera(el) {
    el.title = T("Clica na pista para a controlar · arrasta: rodar a câmara · roda do rato: distância · duplo clique: repor · Esc: largar");
    el.tabIndex = 0;
    let drag = null;
    el.addEventListener("pointerdown", (e) => {
      el.focus({ preventScroll: true });
      if (e.button !== 0) return;
      drag = { x: e.clientX, y: e.clientY, yaw: options.yaw, pitch: options.pitch };
      el.setPointerCapture(e.pointerId);
      el.classList.add("turning");
    });
    el.addEventListener("pointermove", (e) => {
      if (!drag) return;
      turnCamera({ yaw: drag.yaw - (e.clientX - drag.x) * 0.4, pitch: drag.pitch + (e.clientY - drag.y) * 0.3 });
    });
    const end = () => { drag = null; el.classList.remove("turning"); };
    el.addEventListener("pointerup", end);
    el.addEventListener("pointercancel", end);
    el.addEventListener("wheel", (e) => {
      if (document.activeElement !== el) return;  // not clicked yet: the page scrolls
      e.preventDefault();
      turnCamera({ dist: options.dist * Math.exp(e.deltaY * 0.001) });
    }, { passive: false });
    el.addEventListener("dblclick", () => turnCamera(CAMERA_DEFAULT));
    el.addEventListener("keydown", (e) => { if (e.key === "Escape") el.blur(); });
  }

  function createStage(host) {
    const r = resources();
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true });
    } catch {
      throw new Error(T("Este browser não tem WebGL (aceleração gráfica) ativo: a pista 3D não está disponível."));
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.localClippingEnabled = true;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.domElement.className = "hw3d-canvas";
    host.prepend(renderer.domElement);
    wireCamera(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x06080d);
    scene.fog = new THREE.Fog(0x06080d, FAR * 0.5, FAR * 1.02);
    scene.add(new THREE.HemisphereLight(0xbfd2ff, 0x1a1208, 0.9));
    const key = new THREE.DirectionalLight(0xffffff, 1.7);
    key.position.set(3, 9, 7);
    scene.add(key);

    const camera = new THREE.PerspectiveCamera(46, 16 / 9, 0.1, FAR + 30);
    const resize = () => {
      const w = host.clientWidth || 800, h = host.clientHeight || 450;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      // A tall panel needs a wider lens to keep a few frets and the headstock in view.
      camera.fov = camera.aspect < 1 ? 50 + 22 * (1 - camera.aspect) : 46;
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(host);
    resize();

    // Highway into the distance, with a faint line per fret.
    const highway = new THREE.Mesh(new THREE.PlaneGeometry(FRETS + 2, FAR + 2), new THREE.MeshStandardMaterial({ color: 0x0d1220, roughness: 1 }));
    highway.rotation.x = -Math.PI / 2;
    highway.position.set(FRETS / 2, -0.02, NECK_FAR - (FAR + 2) / 2);
    scene.add(highway);
    const pts = [];
    for (let f = 0; f <= FRETS; f += 1) pts.push(f, 0, NECK_FAR, f, 0, -FAR);
    const lines = new THREE.BufferGeometry();
    lines.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    scene.add(new THREE.LineSegments(lines, new THREE.LineBasicMaterial({ color: 0x27304a })));

    // The neck under the strings: rosewood, nickel frets, pearl inlays, fret numbers in front.
    const neck = new THREE.Mesh(new THREE.BoxGeometry(FRETS, 0.12, NECK_NEAR - NECK_FAR), new THREE.MeshStandardMaterial({ map: r.woodTex, roughness: 0.75 }));
    neck.position.set(FRETS / 2, -0.06, (NECK_NEAR + NECK_FAR) / 2);
    scene.add(neck);
    const wireMat = new THREE.MeshStandardMaterial({ color: 0xc8ccd4, metalness: 0.9, roughness: 0.28 });
    const wireGeo = new THREE.BoxGeometry(0.05, 0.05, NECK_NEAR - NECK_FAR);
    for (let f = 1; f <= FRETS; f += 1) {
      const wire = new THREE.Mesh(wireGeo, wireMat);
      wire.position.set(f, 0.02, (NECK_NEAR + NECK_FAR) / 2);
      scene.add(wire);
    }
    const pearl = new THREE.MeshStandardMaterial({ color: 0xe9e4d6, roughness: 0.35, emissive: 0x2a2822 });
    const dotGeo = new THREE.CircleGeometry(0.13, 28);
    for (const f of INLAYS) {
      for (const dz of f % 12 === 0 ? [-0.35, 0.35] : [0]) {
        const dot = new THREE.Mesh(dotGeo, pearl);
        dot.rotation.x = -Math.PI / 2;
        dot.position.set(fretX(f), 0.005, 0.5 + dz);
        scene.add(dot);
      }
    }
    // Fret numbers: as in Rocksmith they light up (amber, with a halo; same place and size) as a
    // note on their fret comes — see lightFrets.
    const fretLabels = [];
    for (let f = 1; f <= FRETS; f += 1) {
      const material = new THREE.SpriteMaterial({ map: textTexture(String(f)), transparent: true, depthWrite: false, opacity: 0.55 });
      const sprite = new THREE.Sprite(material);
      sprite.scale.set(0.5, 0.5, 1);
      sprite.position.set(fretX(f), 0.2, NECK_NEAR + 0.35);
      const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: r.fretGlowTex(String(f)), transparent: true, depthWrite: false, opacity: 0 }));
      halo.scale.set(0.6, 0.6, 1);
      halo.position.set(fretX(f), 0.2, NECK_NEAR + 0.34);
      scene.add(halo, sprite);
      fretLabels[f] = { sprite, halo, lit: -1 };
    }

    // The anchor: the frets the hand is in, lit along the highway.
    const anchor = new THREE.Mesh(new THREE.PlaneGeometry(1, FAR + NECK_NEAR), new THREE.MeshBasicMaterial({ color: 0x3a5cff, transparent: true, opacity: 0.16, depthWrite: false }));
    anchor.rotation.x = -Math.PI / 2;
    anchor.position.set(2.5, 0.012, NECK_NEAR - (FAR + NECK_NEAR) / 2);
    anchor.scale.x = 4;
    scene.add(anchor);
    const edgeMat = new THREE.MeshBasicMaterial({ color: 0x7c98ff, transparent: true, opacity: 0.55, depthWrite: false });
    const edges = [0, 1].map(() => {
      const edge = new THREE.Mesh(new THREE.PlaneGeometry(0.05, FAR + NECK_NEAR), edgeMat);
      edge.rotation.x = -Math.PI / 2;
      edge.position.set(0, 0.014, anchor.position.z);
      scene.add(edge);
      return edge;
    });

    // The hand window at the strings: a frame that lights up when a note strikes (Rocksmith's
    // "hit box"), around the frets of the hand window and every string — see flashWindow.
    const windowFrame = new THREE.Group();
    windowFrame.position.z = 0.07;
    const windowFill = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ color: 0x5f7cff, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
    const windowCore = new THREE.MeshBasicMaterial({ color: 0xdfe6ff, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
    const windowHalo = new THREE.MeshBasicMaterial({ map: r.lineGlowTex, color: 0x7c98ff, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
    // Four sides, each a thin bright core over a soft halo; unit-sized, placed by placeWindow.
    const windowSides = [0, 1, 2, 3].map((i) => {
      const vertical = i >= 2;
      const core = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), windowCore);
      const halo = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), windowHalo);
      if (vertical) halo.rotation.z = Math.PI / 2;
      windowFrame.add(halo, core);
      return { core, halo, vertical };
    });
    windowFrame.add(windowFill);
    windowFrame.visible = false;
    scene.add(windowFrame);

    // Headstock: wooden six-in-line head, bone nut with the tuning written on it, a tuner per string.
    const headstock = new THREE.Group();
    scene.add(headstock);
    const top = stringY(0) + 0.38, bottom = stringY(5) - 0.38;
    const shape = new THREE.Shape();
    shape.moveTo(-NUT_W, bottom);
    shape.lineTo(-3.35, bottom - 0.08);
    shape.quadraticCurveTo(-4.05, bottom + 0.1, -3.95, (top + bottom) / 2);
    shape.quadraticCurveTo(-3.85, top + 0.42, -2.9, top + 0.34);
    shape.lineTo(-NUT_W, top);
    shape.closePath();
    const head = new THREE.Mesh(
      new THREE.ExtrudeGeometry(shape, { depth: 0.14, bevelEnabled: true, bevelThickness: 0.04, bevelSize: 0.05, bevelSegments: 4 }),
      new THREE.MeshStandardMaterial({ map: r.woodTex, color: 0xa0673c, roughness: 0.5 }),
    );
    head.position.z = -0.42;
    headstock.add(head);
    const nut = new THREE.Mesh(
      new THREE.ExtrudeGeometry(roundedRect(NUT_W, top - bottom, 0.06), { depth: 0.22, bevelEnabled: true, bevelThickness: 0.03, bevelSize: 0.03, bevelSegments: 3 }),
      new THREE.MeshStandardMaterial({ color: 0xece4cf, roughness: 0.38 }),
    );
    nut.position.set(-NUT_W / 2, (top + bottom) / 2, -0.2);
    headstock.add(nut);
    const pegMat = new THREE.MeshStandardMaterial({ color: 0xd4d8de, metalness: 0.9, roughness: 0.25 });
    const bushing = new THREE.CylinderGeometry(0.13, 0.13, 0.1, 28).rotateX(Math.PI / 2);
    const post = new THREE.CylinderGeometry(0.055, 0.055, 0.3, 16).rotateX(Math.PI / 2);
    const pegs = [];
    for (let s = 0; s <= 5; s += 1) {
      const b = new THREE.Mesh(bushing, pegMat);
      b.position.set(pegX(s), stringY(s), -0.22);
      const p = new THREE.Mesh(post, pegMat);
      p.position.set(pegX(s), stringY(s), -0.08);
      headstock.add(b, p);
      pegs.push([b, p]);
    }

    // Strings from each tuner to the end of the neck, with a glow band that lights on a hit.
    const strings = [];
    for (let s = 0; s <= 5; s += 1) {
      const x0 = pegX(s), x1 = FRETS + 0.3, length = x1 - x0, radius = 0.045 - s * 0.005;
      const material = new THREE.MeshStandardMaterial({ color: STRING_COLORS[s], emissive: STRING_COLORS[s], emissiveIntensity: 0.35, metalness: 0.4, roughness: 0.35 });
      const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, length, 12).rotateZ(Math.PI / 2), material);
      mesh.position.set((x0 + x1) / 2, stringY(s), 0);
      scene.add(mesh);
      const glowMat = new THREE.MeshBasicMaterial({ map: r.lineGlowTex, color: STRING_COLORS[s], transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
      const glow = new THREE.Mesh(new THREE.PlaneGeometry(FRETS + 1, 0.42), glowMat);
      glow.position.set((FRETS + 1) / 2 - 0.5, stringY(s), 0.03);
      scene.add(glow);
      strings.push({ material, glowMat, glow: 0, mesh, glowMesh: glow, pegs: pegs[s] });
    }

    const lane = new THREE.Group(); // notes, chord frames, bar lines: everything that moves
    scene.add(lane);
    return {
      host, renderer, scene, camera, observer, anchor, edges, headstock, strings, fretLabels, lane,
      nutLabels: [], effects: [], cameraX: 2.5, anchorFirst: 1, anchorWidth: 4, stringCount: 6,
      window: { group: windowFrame, fill: windowFill, core: windowCore, halo: windowHalo, sides: windowSides, glow: 0, first: 1, width: 4 },
    };
  }

  // A bass has four strings: the two it does not have (and their tuners) are hidden.
  function setStringCount(count) {
    stage.stringCount = count;
    stage.strings.forEach((str, s) => {
      const on = s < count;
      str.mesh.visible = on;
      str.glowMesh.visible = on;
      for (const m of str.pegs) m.visible = on;
    });
  }

  function setTuning(offsets, count = 6) {
    for (const m of stage.nutLabels) { stage.headstock.remove(m); m.material.map.dispose(); m.material.dispose(); }
    stage.nutLabels = [];
    // Pitch classes only: a bass's E1 A1 D2 G2 name like the guitar's four lowest strings.
    const names = STANDARD.map((midi, s) => NOTE_NAMES[(((midi + (offsets[s] || 0)) % 12) + 12) % 12]);
    if (count === 6 && names[0] === names[5]) names[5] = names[5].toLowerCase(); // "E … e", as guitarists write it
    setStringCount(count);
    for (let s = 0; s < count; s += 1) {
      const material = new THREE.MeshBasicMaterial({ map: textTexture(names[s], hex(STRING_COLORS[s]), { size: 104, outline: 16 }), transparent: true, depthWrite: false });
      const label = new THREE.Mesh(new THREE.PlaneGeometry(0.42, 0.42), material);
      label.position.set(-NUT_W / 2, stringY(s), 0.054);
      stage.headstock.add(label);
      stage.nutLabels.push(label);
    }
  }

  // --- Song ---------------------------------------------------------------------------------------
  // First index whose time is >= t, in a list sorted by time.
  function lowerBound(list, t, key) {
    let lo = 0, hi = list.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (key(list[mid]) < t) lo = mid + 1; else hi = mid;
    }
    return lo;
  }

  // The fret window the hand is in around time t: the chart's fret-hand position (FHP) there,
  // as the game shows it — else the frets of the notes about to be played.
  function anchorAt(t) {
    const fhps = song.fhps;
    if (fhps.length) {
      const h = fhps[Math.max(0, lowerBound(fhps, t + 0.005, (x) => x.t) - 1)];
      return { first: h.fret, width: h.width };
    }
    const notes = song.notes;
    let first = Infinity, last = -Infinity;
    for (let i = lowerBound(notes, t - 0.1, (n) => n.t); i < notes.length && notes[i].t <= t + ANCHOR_AHEAD; i += 1) {
      const f = notes[i].fret;
      if (f > 0) { first = Math.min(first, f); last = Math.max(last, f); }
    }
    if (first === Infinity) return null;
    return { first, width: Math.max(4, last - first + 1) };
  }

  // A bend's curve as [seconds after the attack, semitones], starting from the attack: a curve
  // whose first point comes later starts unbent (a plain bend is one point at the note's end).
  function bendPoints(n) {
    if (!(n.bend > 0)) return [];
    let curve = (Array.isArray(n.bendCurve) ? n.bendCurve : [])
      .filter((p) => Array.isArray(p) && Number.isFinite(p[0]) && Number.isFinite(p[1]))
      .map((p) => [Math.max(0, p[0]), Math.max(0, Math.min(BEND_MAX, p[1]))])
      .sort((a, b) => a[0] - b[0]);
    if (!curve.length) curve = [[Math.max(n.sustain || 0, 0.1), Math.min(BEND_MAX, n.bend)]];
    if (curve[0][0] > 0.005) curve.unshift([0, 0]);
    return curve;
  }
  // Semitones bent `dt` seconds after the attack: straight between the points, held after the last.
  function bendAt(curve, dt) {
    if (!curve.length) return 0;
    if (dt <= curve[0][0]) return curve[0][1];
    for (let i = 1; i < curve.length; i += 1) {
      const [t1, v1] = curve[i];
      if (dt <= t1) {
        const [t0, v0] = curve[i - 1];
        return t1 > t0 ? v0 + ((v1 - v0) * (dt - t0)) / (t1 - t0) : v1;
      }
    }
    return curve[curve.length - 1][1];
  }

  function disposeSong() {
    if (!song) return;
    for (const obj of song.live.values()) stage.lane.remove(obj.group);
    for (const obj of song.liveLines.values()) stage.lane.remove(obj);
    for (const g of song.owned) g.dispose();
    song = null;
  }

  function buildSong(data) {
    disposeSong();
    const count = data.strings === 4 ? 4 : 6;
    const notes = (data.notes || []).filter((n) => n.string >= 0 && n.string < count && Number.isFinite(n.t))
      .map((n) => ({ ...n, bendCurve: bendPoints(n) }))
      .sort((a, b) => a.t - b.t || a.string - b.string);
    // Chords: notes struck together (the score's own grouping), with the name it derived.
    const chords = [];
    for (let i = 0; i < notes.length;) {
      let j = i + 1;
      while (j < notes.length && notes[j].t - notes[i].t < CHORD_EPS) j += 1;
      if (j - i >= 2) {
        const chord = { t: notes[i].t, members: notes.slice(i, j), name: notes.slice(i, j).map((n) => n.chordName).find(Boolean) || "" };
        for (const n of chord.members) n.chord = chord;
        chords.push(chord);
      }
      i = j;
    }
    const lines = [
      ...(data.beats || []).map((t) => ({ t, bar: false })),
      ...(data.bars || []).map((b) => ({ t: b.t, bar: true, measure: b.measure })),
      ...(data.sections || []).map((s) => ({ t: s.t, section: s.name })),
    ].filter((l) => Number.isFinite(l.t)).sort((a, b) => a.t - b.t);
    const maxSustain = notes.reduce((m, n) => Math.max(m, n.sustain || 0), 0);
    const fhps = (data.fhps || []).filter((h) => Number.isFinite(h.t)).slice().sort((a, b) => a.t - b.t);
    song = { notes, chords, lines, fhps, live: new Map(), liveLines: new Map(), owned: [], back: Math.min(8, maxSustain) + 0.8 };
    setTuning(data.tuning || [0, 0, 0, 0, 0, 0], count);
    lastNow = null;
  }

  // The note's face: the fret number (only with "Fret on the note"; Rocksmith lights the neck's
  // fret number instead), X for a fret-hand mute, the hammer-on / pull-off arrow beside the number
  // — on the face, so it reads while the note strikes the string however fast the passage — and
  // the accent's double frame around the note.
  function addFace(group, n, width, materials = null) {
    const r = resources();
    const own = (material) => {
      if (!materials) return material;
      const copy = material.clone(); // a held note fades its own copy
      copy.clippingPlanes = null;
      materials.push(copy);
      return copy;
    };
    const muted = n.techniques.includes("mute");
    if (n.fret > 0) {
      const decal = new THREE.Mesh(r.square, own(r.faceMat(muted ? "X" : String(n.fret))));
      decal.scale.set(0.34, 0.34, 1);
      decal.position.z = 0.125;
      decal.userData.number = !muted; // X always shows
      decal.visible = muted || options.numbers;
      group.add(decal);
    }
    const legato = LEGATO.find((tech) => n.techniques.includes(tech));
    if (legato) {
      const arrow = new THREE.Mesh(r.square, own(r.iconMat(legato)));
      arrow.scale.set(0.24, 0.24, 1);
      arrow.position.z = 0.126;
      arrow.userData.arrow = true;
      group.add(arrow);
    }
    if (n.techniques.includes("accent")) {
      const frame = new THREE.Mesh(r.square, own(r.accentMat));
      frame.scale.set(n.fret > 0 ? 1.1 : width + 0.35, 0.6, 1);
      frame.position.z = 0.124;
      group.add(frame);
    }
    layoutFace(group);
  }
  // The arrow sits beside a shown number, or in the middle of the face.
  function layoutFace(group) {
    const shown = group.children.some((o) => o.userData.number && o.visible) ||
      group.children.some((o) => o.userData.number === false); // an X
    for (const o of group.children) {
      if (o.userData.arrow) o.position.x = shown ? 0.2 : 0;
      else if (o.userData.number !== undefined) o.position.x = group.children.some((c) => c.userData.arrow) ? -0.09 : 0;
    }
  }

  // Symbols above the note (side by side) and a bend's chevrons above them.
  function addMarks(group, n) {
    const r = resources();
    const kinds = ABOVE.filter((tech) => n.techniques.includes(tech));
    kinds.forEach((kind, k) => {
      const icon = new THREE.Mesh(r.square, r.iconMat(kind));
      icon.scale.set(0.34, 0.34, 1);
      icon.position.set((k - (kinds.length - 1) / 2) * 0.38, 0.38, 0);
      group.add(icon);
    });
    let y = kinds.length ? 0.74 : 0.38;
    if (n.bend > 0) {
      const icon = new THREE.Mesh(r.square, r.iconMat(`bend${n.bend <= 1 ? 1 : n.bend <= 2 ? 2 : 3}|#3ddcc4`));
      icon.scale.set(0.34, 0.34, 1);
      icon.position.set(0, y, 0);
      group.add(icon);
      y += 0.36;
    }
    if (n.techniques.includes("letRing")) {
      const label = new THREE.Mesh(r.square, r.markMat("LR"));
      label.scale.set(0.8, 0.4, 1);
      label.position.set(0, y, 0);
      group.add(label);
    }
  }

  // How far along its slide a trail is at `u` (0…1 of its `length` on the highway): straight in the
  // middle, with a small curve at each end (the trail leaves its note, and meets the note it slides
  // to, running along the highway), so it flows into them instead of meeting them at a corner.
  // The curves take SLIDE_BLEND of the length each, at most SLIDE_BLEND_MAX highway units.
  function slideShare(u, length) {
    const b = Math.min(SLIDE_BLEND, SLIDE_BLEND_MAX / Math.max(length, 1e-6));
    const m = 1 / (1 - b); // the slope of the straight middle
    if (u < b) return (m * u * u) / (2 * b);
    if (u > 1 - b) return 1 - (m * (1 - u) * (1 - u)) / (2 * b);
    return m * (u - b / 2);
  }

  // A sustain trail lying on the string's plane, one unit long (scaled to the sustain): flat, wavy
  // with vibrato, a zigzag with tremolo picking; a slide runs it to the fret it ends on; a bend
  // lifts it along the bend's curve over its `span` seconds.
  function trailGeometry(n, length, dx, span = 0) {
    const tremolo = n.techniques.includes("tremolo");
    const vibrato = !tremolo && n.techniques.includes("vibrato");
    const bent = n.bendCurve && n.bendCurve.length > 0;
    const hw = tremolo || vibrato ? 0.08 : 0.12;
    let steps = tremolo ? Math.max(2, Math.round(length / 0.3)) : vibrato ? Math.max(2, Math.round(length / 0.06)) : 1;
    if (bent) steps = Math.max(steps, 32);
    if (dx) steps = Math.max(steps, 24); // a slide: room for its curved ends
    const positions = [], index = [];
    for (let k = 0; k <= steps; k += 1) {
      const u = k / steps;
      let side = 0;
      if (tremolo && k > 0) side = k % 2 ? 0.16 : -0.16;
      if (vibrato) side = 0.12 * Math.sin(u * length * 4);
      const x = dx * slideShare(u, length) + side;
      const y = bent ? BEND_Y * bendAt(n.bendCurve, u * span) : 0;
      positions.push(x - hw, y, -u, x + hw, y, -u);
      if (k) index.push(2 * k - 2, 2 * k, 2 * k - 1, 2 * k - 1, 2 * k, 2 * k + 1);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    g.setIndex(index);
    g.computeVertexNormals();
    return g;
  }

  function makeNote(n) {
    const r = resources();
    const group = new THREE.Group();
    // The note itself (outline, face, marks) turns as it comes; its drop line and trail do not.
    const head = new THREE.Group();
    group.add(head);
    group.userData.head = head;
    const s = n.string;
    const muted = n.techniques.includes("mute");
    const mats = muted ? r.mutedOutlineMats : r.outlineMats[s];
    let x = fretX(n.fret), width = 1;
    if (n.fret === 0) {
      // Open string: a bar across the hand's window, as Rocksmith draws it.
      const a = anchorAt(n.t) || { first: stage.anchorFirst, width: stage.anchorWidth };
      width = a.width;
      x = a.first - 1 + a.width / 2;
      addOutline(head, r.openOutline(Math.round((a.width - 0.15) * 4) / 4), mats);
      addPalmMute(head, n, a.width, r.crossMats[s]);
    } else {
      addOutline(head, r.noteOutline, mats);
      addPalmMute(head, n, 1, r.crossMats[s]);
      // Drop line to the highway, under the fret it is played on.
      const h = stringY(s) - 0.15;
      const stem = new THREE.Mesh(r.square, r.stemMats[s]);
      stem.scale.set(0.035, h, 1);
      stem.position.set(0, -0.15 - h / 2, -0.02);
      group.add(stem);
    }
    addFace(head, n, width);
    addMarks(head, n);
    let trail = null;
    // A short note with vibrato, tremolo picking or a bend still gets a trail, to show it; a
    // bend's runs as long as its curve.
    const wavy = n.techniques.includes("vibrato") || n.techniques.includes("tremolo");
    const bent = n.bendCurve.length > 0;
    const span = Math.max(n.sustain || 0, wavy ? 0.4 : 0, bent ? n.bendCurve[n.bendCurve.length - 1][0] : 0);
    const trailLength = span * SPEED;
    if (trailLength > 0.05 * SPEED) {
      const dx = n.slideTo >= 0 && n.fret > 0 ? fretX(n.slideTo) - x : 0;
      const g = trailGeometry(n, trailLength, dx, span);
      song.owned.push(g);
      trail = new THREE.Mesh(g, bent ? r.bendTrailMat : r.trailMats[s]);
      group.add(trail);
    }
    stage.lane.add(group);
    return { group, head, trail, trailLength, x, width, note: n };
  }

  // The box around a chord's notes: its frame, and the centre the chord turns around.
  function chordBox(c) {
    const frets = c.members.map((n) => n.fret).filter((f) => f > 0);
    const ys = c.members.map((n) => stringY(n.string));
    let left = frets.length ? Math.min(...frets) - 1 - 0.08 : Infinity;
    let right = frets.length ? Math.max(...frets) + 0.08 : -Infinity;
    if (c.members.some((n) => n.fret === 0)) { // an open string spans the whole hand position
      const a = anchorAt(c.t) || { first: stage.anchorFirst, width: stage.anchorWidth };
      left = Math.min(left, a.first - 1 - 0.08); right = Math.max(right, a.first - 1 + a.width + 0.08);
    }
    const top = Math.max(...ys) + 0.3, bottom = Math.min(...ys) - 0.3;
    return { left, right, top, bottom, cx: (left + right) / 2, cy: (top + bottom) / 2 };
  }
  function makeChordFrame(c) {
    const r = resources();
    const { left, right, top, bottom, cx, cy } = c.box || (c.box = chordBox(c));
    const outer = roundedRect(right - left, top - bottom, 0.12);
    outer.holes.push(roundedRect(right - left - 0.09, top - bottom - 0.09, 0.08));
    const geometry = new THREE.ShapeGeometry(outer, 8);
    song.owned.push(geometry);
    const group = new THREE.Group();
    group.add(new THREE.Mesh(geometry, r.frameMat));
    if (c.name) {
      const label = new THREE.Mesh(r.square, r.markMat(c.name));
      label.scale.set(1.8, 0.9, 1);
      label.position.set(0, (top - bottom) / 2 + 0.36, 0);
      group.add(label);
    }
    group.position.set(cx, cy, 0);
    stage.lane.add(group);
    return { group, trail: null };
  }

  function makeLine(l) {
    const r = resources();
    if (l.section) {
      const label = new THREE.Mesh(r.square, r.labelMat(`#3ddcc4|${l.section}`));
      label.scale.set(3.2, 0.8, 1);
      label.rotation.x = -Math.PI / 2;
      label.position.set(-2.2, 0.02, 0);
      stage.lane.add(label);
      return label;
    }
    const group = new THREE.Group();
    const line = new THREE.Mesh(r.square, l.bar ? r.barMat : r.beatMat);
    // Lying on the floor, a line is seen almost edge-on: thin ones vanish below a pixel.
    line.scale.set(FRETS, l.bar ? 0.3 : 0.13, 1);
    line.rotation.x = -Math.PI / 2;
    line.position.set(FRETS / 2, 0.01, 0);
    group.add(line);
    if (l.bar) {
      const number = new THREE.Mesh(r.square, r.labelMat(`#8d97ad|${l.measure}`));
      number.scale.set(1.6, 0.4, 1);
      number.rotation.x = -Math.PI / 2;
      number.position.set(-0.9, 0.02, 0);
      group.add(number);
    }
    stage.lane.add(group);
    return group;
  }

  // --- Hits: a little glow, and the note stays on the string ------------------------------------------
  function heldNote(obj) {
    const r = resources();
    const n = obj.note;
    const group = new THREE.Group();
    const color = n.techniques.includes("mute") ? 0x8a90a0 : STRING_COLORS[n.string];
    // Lit on the string: the same outline, brighter, with its own materials so it can fade.
    const mats = outlineMats(color, null, true);
    const materials = [mats.ring, mats.halo, mats.fill];
    addOutline(group, n.fret === 0 ? r.openOutline(Math.round((obj.width - 0.15) * 4) / 4) : r.noteOutline, mats);
    const crossMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.55, depthWrite: false });
    addPalmMute(group, n, obj.width, crossMat);
    materials.push(crossMat);
    addFace(group, n, obj.width, materials);
    group.position.set(obj.x, stringY(n.string), 0.02);
    stage.scene.add(group);
    let bend = null;
    if (n.bendCurve.length) {
      // A bend: a teal line from the string to the note as it rises, and the frame it rises into.
      const peak = Math.max(...n.bendCurve.map((p) => p[1]));
      const pushMat = new THREE.MeshBasicMaterial({ map: r.lineGlowTex, color: TEAL, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
      const push = new THREE.Mesh(r.square, pushMat);
      push.rotation.z = Math.PI / 2; // the glow runs across the texture's height: along the line
      const targetMat = new THREE.MeshBasicMaterial({ map: r.bendTargetTex, transparent: true, opacity: 0.9, depthWrite: false });
      const target = new THREE.Mesh(r.square, targetMat);
      target.scale.set(Math.max(0.95, obj.width + 0.2), 0.5, 1);
      target.position.set(obj.x, stringY(n.string) + BEND_Y * peak, 0.01);
      stage.scene.add(push, target);
      materials.push(pushMat, targetMat);
      bend = { push, pushMat, target, curve: n.bendCurve, t0: n.t, dy: 0 };
    }
    return { group, materials, bend };
  }

  // The frame around the hand window lights up as a note (or chord) strikes: the window of that
  // moment — the chart's FHP there, else the frets being played — over every string.
  function flashWindow(t) {
    const w = stage.window;
    const a = anchorAt(t) || { first: stage.anchorFirst, width: stage.anchorWidth };
    w.first = a.first;
    w.width = a.width;
    w.glow = 1;
    placeWindow();
  }
  function placeWindow() {
    const w = stage.window;
    const top = stringY(0) + 0.3, bottom = stringY(stage.stringCount - 1) - 0.3;
    const left = w.first - 1, right = w.first - 1 + w.width;
    const cx = (left + right) / 2, cy = (top + bottom) / 2, wd = right - left, ht = top - bottom;
    const CORE = 0.05, HALO = 0.42;
    w.fill.position.set(cx, cy, -0.01);
    w.fill.scale.set(wd, ht, 1);
    w.sides.forEach((side, i) => {
      if (side.vertical) {
        const x = i === 2 ? left : right;
        side.core.position.set(x, cy, 0);
        side.core.scale.set(CORE, ht + CORE, 1);
        side.halo.position.set(x, cy, -0.005);
        side.halo.scale.set(ht + HALO, HALO, 1); // rotated a quarter turn: x is its height
      } else {
        const y = i === 0 ? top : bottom;
        side.core.position.set(cx, y, 0);
        side.core.scale.set(wd + CORE, CORE, 1);
        side.halo.position.set(cx, y, -0.005);
        side.halo.scale.set(wd + HALO, HALO, 1);
      }
    });
  }

  function hit(obj) {
    const r = resources();
    const n = obj.note, s = n.string, color = STRING_COLORS[s];
    stage.strings[s].glow = 1;
    flashWindow(n.t);
    const flash = new THREE.Sprite(new THREE.SpriteMaterial({ map: r.glowTex, color, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
    const core = new THREE.Sprite(new THREE.SpriteMaterial({ map: r.glowTex, color: 0xffffff, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
    flash.position.set(obj.x, stringY(s), 0.08);
    core.position.copy(flash.position);
    stage.scene.add(flash, core);
    const count = 14, positions = new Float32Array(count * 3), velocities = [];
    for (let i = 0; i < count; i += 1) {
      positions.set([obj.x + (Math.random() - 0.5) * 0.5 * obj.width, stringY(s), 0.05], i * 3);
      velocities.push([(Math.random() - 0.5) * 2.2, 1.2 + Math.random() * 2.4, 0.6 + Math.random() * 1.2]);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const sparks = new THREE.Points(geo, new THREE.PointsMaterial({ color, size: 0.09, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
    stage.scene.add(sparks);
    stage.effects.push({
      flash, core, sparks, velocities, age: 0, width: obj.width, hold: n.sustain || 0, string: s,
      held: heldNote(obj), keep: Math.max(HOLD_MIN, n.sustain || 0),
    });
  }

  function clearEffects() {
    for (const e of stage.effects) removeEffect(e);
    stage.effects = [];
    stage.window.glow = 0;
    stage.window.group.visible = false;
  }
  function removeEffect(e) {
    stage.scene.remove(e.flash, e.core, e.sparks, e.held.group);
    if (e.held.bend) stage.scene.remove(e.held.bend.push, e.held.bend.target);
    e.flash.material.dispose(); e.core.material.dispose(); e.sparks.material.dispose(); e.sparks.geometry.dispose();
    for (const m of e.held.materials) m.dispose();
  }

  function updateEffects(dt, now) {
    const effects = stage.effects;
    for (let i = effects.length - 1; i >= 0; i -= 1) {
      const e = effects[i];
      e.age += dt;
      const k = Math.min(e.age / 0.45, 1);
      const holding = e.age < e.hold;
      const pulse = holding ? 0.75 + 0.25 * Math.sin(e.age * 30) : 1 - k;
      e.flash.scale.set((0.9 + 1.6 * k) * e.width, 0.9 + 1.2 * k, 1);
      e.flash.material.opacity = holding ? 0.55 * pulse : 0.9 * (1 - k);
      e.core.scale.set(0.45 * e.width + 0.2, 0.45, 1);
      e.core.material.opacity = holding ? 0.8 * pulse : 1 - k;
      if (holding) {
        stage.strings[e.string].glow = Math.max(stage.strings[e.string].glow, 0.55 + 0.2 * pulse);
        stage.window.glow = Math.max(stage.window.glow, 0.45 + 0.15 * pulse);
      }
      const pos = e.sparks.geometry.attributes.position;
      for (let j = 0; j < e.velocities.length; j += 1) {
        const v = e.velocities[j];
        v[1] -= 6 * dt;
        pos.array[j * 3] += v[0] * dt; pos.array[j * 3 + 1] += v[1] * dt; pos.array[j * 3 + 2] += v[2] * dt;
      }
      pos.needsUpdate = true;
      e.sparks.material.opacity = Math.max(0, 1 - e.age / 0.6);
      const pop = 1 + 0.18 * Math.max(0, 1 - e.age / 0.12);
      e.held.group.scale.set(pop, pop, pop);
      const fade = e.age <= e.keep ? 1 : Math.max(0, 1 - (e.age - e.keep) / FADE);
      for (const m of e.held.materials) {
        if (m.userData.base === undefined) m.userData.base = m.opacity;
        m.opacity = m.userData.base * fade * (holding ? 0.8 + 0.2 * pulse : 1);
      }
      const b = e.held.bend;
      if (b) {
        // The note rises on the string as it is bent, in the song's own clock (a pause holds it).
        const dy = BEND_Y * bendAt(b.curve, Math.max(0, now - b.t0));
        b.dy = dy;
        const y = stringY(e.string);
        e.held.group.position.y = y + dy;
        e.flash.position.y = y + dy;
        e.core.position.y = y + dy;
        b.push.visible = dy > 0.01;
        b.push.scale.set(Math.max(dy, 0.01), 0.28, 1);
        b.push.position.set(e.held.group.position.x, y + dy / 2, 0.015);
        b.pushMat.opacity = 0.95 * fade;
        b.target.material.opacity = 0.9 * fade;
      }
      if (!holding && e.age >= Math.max(0.6, e.keep + FADE)) {
        removeEffect(e);
        effects.splice(i, 1);
      }
    }
    for (const st of stage.strings) {
      st.glow = Math.max(0, st.glow - dt * 2.2);
      st.material.emissiveIntensity = 0.35 + 2.2 * st.glow;
      st.glowMat.opacity = 0.85 * st.glow;
    }
    const w = stage.window;
    w.glow = Math.max(0, w.glow - dt * 1.8);
    w.group.visible = w.glow > 0.01;
    w.core.opacity = 0.95 * w.glow;
    w.halo.opacity = 0.9 * w.glow;
    w.fill.material.opacity = 0.14 * w.glow;
  }

  // A fret number of the neck lights up (amber, with a halo) as a note on that fret comes —
  // faint FRET_RAMP seconds before, fully when it strikes — stays lit while the note sounds, then
  // fades. It never moves or changes size.
  let fretShades = null; // [white, amber], made once three.js is loaded
  function lightFrets(now) {
    if (!fretShades) fretShades = [new THREE.Color(0xffffff), new THREE.Color(AMBER)];
    const light = new Array(FRETS + 1).fill(0);
    if (song) {
      const notes = song.notes;
      for (let i = lowerBound(notes, now - song.back, (n) => n.t); i < notes.length && notes[i].t <= now + FRET_RAMP; i += 1) {
        const n = notes[i];
        if (n.fret < 1 || n.fret > FRETS || n.techniques.includes("mute")) continue;
        let level;
        if (n.t > now) level = (1 - (n.t - now) / FRET_RAMP) ** 2;
        else {
          const end = n.t + Math.max(n.sustain || 0, HOLD_MIN);
          level = now <= end ? 1 : 1 - (now - end) / FADE;
        }
        if (level > light[n.fret]) light[n.fret] = level;
      }
    }
    for (let f = 1; f <= FRETS; f += 1) {
      const l = stage.fretLabels[f];
      const level = Math.max(0, Math.min(1, light[f]));
      if (Math.abs(level - l.lit) < 0.005) continue;
      l.lit = level;
      l.sprite.material.opacity = 0.55 + 0.45 * level;
      l.sprite.material.color.lerpColors(fretShades[0], fretShades[1], level);
      l.halo.material.opacity = level;
    }
  }

  // Turn a note's head by `angle`: around its own centre, or, in a chord, around the chord's
  // centre, so the chord turns as one piece with its frame.
  function rollNote(obj, angle) {
    const head = obj.head;
    if (!head) return;
    head.rotation.z = angle;
    const chord = obj.note.chord;
    const box = chord && (chord.box || (song && (chord.box = chordBox(chord))));
    if (!box || !angle) { head.position.set(0, 0, 0); return; }
    const dx = obj.x - box.cx, dy = stringY(obj.note.string) - box.cy;
    const c = Math.cos(angle), s = Math.sin(angle);
    head.position.set(dx * c - dy * s - dx, dx * s + dy * c - dy, 0);
  }

  // --- Frame --------------------------------------------------------------------------------------
  function frame(ms) {
    raf = requestAnimationFrame(frame);
    const dt = lastFrame ? Math.min((ms - lastFrame) / 1000, 0.1) : 0;
    lastFrame = ms;
    let now = 0, playing = false;
    try { ({ t: now, playing } = getNow()); } catch { /* keep the last frame's time */ }
    if (!Number.isFinite(now)) now = 0;

    if (song) {
      // A jump (seek, a new sync preview) must not fire a burst of old hits.
      const jumped = lastNow === null || now < lastNow - 0.05 || now > lastNow + 0.5;
      if (jumped) clearEffects();
      const from = now - song.back, to = now + AHEAD + 0.4;
      // Notes and chord frames in view: create what just came into view, drop what left it.
      const wanted = new Set();
      const notes = song.notes;
      for (let i = lowerBound(notes, from, (n) => n.t); i < notes.length && notes[i].t <= to; i += 1) {
        const n = notes[i];
        if (n.t + (n.sustain || 0) < now - 0.1) continue;
        const key = `n${i}`;
        wanted.add(key);
        let obj = song.live.get(key);
        if (!obj) { obj = makeNote(n); song.live.set(key, obj); }
        obj.group.position.set(obj.x, stringY(n.string), -(n.t - now) * SPEED);
        rollNote(obj, comesLevel(n) ? 0 : noteRoll(n.t - now));
        if (obj.trail) obj.trail.scale.z = obj.trailLength;
        if (!jumped && playing && lastNow < n.t && n.t <= now && now - n.t < 0.25) hit(obj);
      }
      const chords = song.chords;
      for (let i = lowerBound(chords, now - 0.3, (c) => c.t); i < chords.length && chords[i].t <= to; i += 1) {
        const key = `c${i}`;
        wanted.add(key);
        let obj = song.live.get(key);
        if (!obj) { obj = makeChordFrame(chords[i]); song.live.set(key, obj); }
        obj.group.position.z = -(chords[i].t - now) * SPEED;
        obj.group.rotation.z = chords[i].members.some((m) => m.fret === 0) ? 0 : noteRoll(chords[i].t - now);
      }
      for (const [key, obj] of song.live) {
        if (!wanted.has(key)) { stage.lane.remove(obj.group); song.live.delete(key); }
      }
      const lines = song.lines, wantedLines = new Set();
      for (let i = lowerBound(lines, now - 0.2, (l) => l.t); i < lines.length && lines[i].t <= to; i += 1) {
        wantedLines.add(i);
        let obj = song.liveLines.get(i);
        if (!obj) { obj = makeLine(lines[i]); song.liveLines.set(i, obj); }
        obj.position.z = -(lines[i].t - now) * SPEED;
      }
      for (const [i, obj] of song.liveLines) {
        if (!wantedLines.has(i)) { stage.lane.remove(obj); song.liveLines.delete(i); }
      }
      // The hand window, a little ahead of the notes, and the camera following it.
      const a = anchorAt(now + 0.15);
      if (a) { stage.anchorFirst = a.first; stage.anchorWidth = a.width; }
      const targetX = stage.anchorFirst - 1 + stage.anchorWidth / 2;
      const ease = jumped ? 1 : Math.min(1, dt * 6);
      stage.anchor.scale.x += (stage.anchorWidth - stage.anchor.scale.x) * ease;
      stage.anchor.position.x += (targetX - stage.anchor.position.x) * ease;
      stage.edges[0].position.x = stage.anchor.position.x - stage.anchor.scale.x / 2;
      stage.edges[1].position.x = stage.anchor.position.x + stage.anchor.scale.x / 2;
      stage.cameraX += (targetX - 0.4 - stage.cameraX) * (jumped ? 1 : Math.min(1, dt * 2.5));
      lastNow = now;
    }
    // Short of 90: straight down, "up" would be undefined and the view would spin.
    const yaw = (options.yaw * Math.PI) / 180, pitch = (Math.min(options.pitch, 89.9) * Math.PI) / 180;
    const px = stage.cameraX + 0.2, flat = options.dist * Math.cos(pitch);
    stage.camera.position.set(px + flat * Math.sin(yaw), PIVOT_Y + options.dist * Math.sin(pitch), PIVOT_Z + flat * Math.cos(yaw));
    stage.camera.lookAt(px, PIVOT_Y, PIVOT_Z);
    updateEffects(dt, now);
    lightFrets(now);
    stage.renderer.render(stage.scene, stage.camera);
  }

  let openGen = 0;  // each open/close; an open that finds it moved on gives up

  // --- Public -------------------------------------------------------------------------------------
  window.Highway3D = {
    // Show the highway in `host`; getNow() answers {t, playing} in the notes' clock;
    // cameraChanged({yaw, pitch, dist}) hears when the camera is turned on the canvas.
    async open(host, now, cameraChanged = null) {
      getNow = now;
      onCamera = cameraChanged;
      const opening = ++openGen;
      await load();
      // closed while three.js was still loading (toggled off, project left):
      // starting now would draw on a hidden panel for good
      if (opening !== openGen) return;
      if (!stage || stage.host !== host) stage = createStage(host);
      if (!raf) { lastFrame = 0; raf = requestAnimationFrame(frame); }
    },
    // Stop drawing (the panel was hidden); the scene is kept for a quick reopen.
    close() {
      openGen++;
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
      if (stage) clearEffects();
      lastNow = null;
    },
    get ready() { return !!stage; },
    // What is on the highway right now (for checking it from the console).
    stats() {
      return song ? {
        notes: song.notes.length, lines: song.lines.length, liveNotes: song.live.size, liveLines: song.liveLines.size,
        window: { glow: stage.window.glow, first: stage.window.first, width: stage.window.width },
        bends: stage.effects.filter((e) => e.held.bend).map((e) => ({ string: e.string, rise: e.held.bend.dy / BEND_Y })),
        rolls: [...song.live.values()].filter((o) => o.head).map((o) => ({ t: o.note.t, string: o.note.string, deg: o.head.rotation.z * 180 / Math.PI })),
      } : null;
    },
    // notes: [{t, sustain, string, fret, techniques, bend, bendCurve, slideTo, chordName}] in the
    // display clock (bendCurve: [[seconds after the attack, semitones]…], optional); bars: [{t, measure}]; beats: [t]; sections: [{t, name}]; tuning: 6 offsets;
    // strings: 6, or 4 for a bass.
    setSong(data) {
      if (!stage) return;
      buildSong(data);
    },
    get cameraDefault() { return { ...CAMERA_DEFAULT }; },
    // numbers: the fret on the note; yaw/pitch (degrees) and dist: the camera.
    setOptions(next) {
      options = { ...options, ...next };
      options = { ...options, ...clampCamera(options) };
      if (!stage) return;
      const show = (obj) => {
        obj.traverse((o) => { if (o.userData.number) o.visible = options.numbers; });
        layoutFace(obj.userData.head || obj);
      };
      stage.lane.children.forEach(show);
      for (const e of stage.effects) show(e.held.group);
    },
    fullscreen() {
      if (!stage) return;
      const el = stage.host;
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
      else if (el.requestFullscreen) el.requestFullscreen().catch(() => {});
    },
  };
})();
