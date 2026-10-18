-- One row per RockForge install and version it reached, sent only by installs
-- whose user agreed (Definições → Geral). No IP, no name, no machine data:
-- a random id the app generated, the version, how it was installed, the OS family.
create table public.install_versions (
  install_id uuid not null,
  version text not null check (char_length(version) between 1 and 40),
  kind text not null check (kind in ('exe', 'git', 'source')),
  os text not null check (os in ('windows', 'macos', 'linux', 'other')),
  first_seen timestamptz not null default now(),
  primary key (install_id, version)
);
comment on table public.install_versions is
  'RockForge opt-in install counter. Written only by the install-ping edge function (service role).';

alter table public.install_versions enable row level security;
-- No policies: nobody reads or writes it through the Data API; the edge function
-- uses the service role.
revoke all on table public.install_versions from anon, authenticated;

create function public.install_counts()
returns json
language sql
stable
security invoker
set search_path = ''
as $$
  select json_build_object(
    'installs', (select count(distinct install_id) from public.install_versions),
    'by_version', coalesce((
      select json_object_agg(version, n order by version)
      from (select version, count(*) as n from public.install_versions group by version) v
    ), '{}'::json),
    'by_kind', coalesce((
      select json_object_agg(kind, n)
      from (select kind, count(distinct install_id) as n from public.install_versions group by kind) k
    ), '{}'::json),
    'by_os', coalesce((
      select json_object_agg(os, n)
      from (select os, count(distinct install_id) as n from public.install_versions group by os) o
    ), '{}'::json)
  );
$$;
revoke execute on function public.install_counts() from public, anon, authenticated;
grant execute on function public.install_counts() to service_role;
