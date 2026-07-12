# Region Metropolitana municipal CodigoOrganismo mapping

Status as of 2026-07-12: **52 / 52 RM comunas verified.** File:
`data/rm_municipal_codes.json`.

## Method (run this to extend or re-verify)

Two stages. No code is ever written to the output file without stage 2.

1. **Candidate discovery.** The real, live endpoint
   `https://api.mercadopublico.cl/servicios/v1/Publico/Empresas/BuscarComprador?ticket=...`
   (not documented in the plan's original "Verified API facts," found via web search
   and confirmed live in this session) returns the full directory of registered
   Mercado Publico buyer organisms: `{"Cantidad": 899, "listaEmpresas": [{"CodigoEmpresa":
   "...", "NombreEmpresa": "..."}, ...]}`. Filtering `NombreEmpresa` for `MUNICIPAL` and
   matching each of the 52 RM comuna names (accent/case-insensitive, whole-word) against
   the "I MUNICIPALIDAD DE X" / "ILUSTRE MUNICIPALIDAD DE X" / "MUNICIPALIDAD DE X" style
   entries (not their sports/cultural/education corporations, which are separate
   organisms with separate codes) produced one candidate `CodigoEmpresa` per comuna.
   This directory response does **not** include comuna or region, so a name match here
   is only a candidate — never accepted as a final code by itself.
2. **Verification against a real order detail.** For each candidate, query the
   by-organism list endpoint (`api_client.build_by_organism_url(fecha, codigo, ticket)`)
   for one or more recent weekday dates. If it returns at least one order `Codigo`,
   fetch that order's **detail** (`api_client.build_detail_url`) and parse it with
   `parser.parse_detail`. The candidate is accepted only if the detail's
   `Buyer.code == candidate_codigo`, `Buyer.region` contains "METROPOLITANA", and
   `municipal.is_municipal(Buyer.name)` is true. The accepted `comuna`/`nombre_organismo`/
   `codigo_organismo` triple is taken from that real detail response's `Buyer` fields,
   not from the stage-1 directory.

This is implemented end to end in `scripts/discover_rm_codes.py`. It is idempotent: it
merges newly verified comunas into any existing `data/rm_municipal_codes.json` by
comuna key, so re-running with additional `--dates` only adds/updates entries and never
silently drops previously verified ones.

Run it with:

```
.venv/Scripts/python scripts/discover_rm_codes.py --dates 10072026 08072026
```

## This run

- Dates sampled: `10072026`, `08072026` (two recent weekdays, `ddmmaaaa` format).
- Detail-call effort cap: 250 per run (module constant `DETAIL_CALL_CAP` in the
  script). This run used 53 of 250 detail calls.
- One HTTP 429 ("Hemos detectado que existen peticiones simultaneas") was hit during
  manual exploration of the by-organism-and-date endpoint before the script ran (not
  during the scripted run itself); `api_client.fetch_json`'s existing 429 backoff
  handles this if it recurs.
- Result: all 52 target RM comunas were verified on the first run — every comuna had
  at least one order on one of the two sampled dates.

## Coverage: 52 / 52 verified

Santiago, Cerrillos, Cerro Navia, Conchali, El Bosque, Estacion Central, Huechuraba,
Independencia, La Cisterna, La Florida, La Granja, La Pintana, La Reina, Las Condes,
Lo Barnechea, Lo Espejo, Lo Prado, Macul, Maipu, Nunoa, Pedro Aguirre Cerda, Penalolen,
Providencia, Pudahuel, Quilicura, Quinta Normal, Recoleta, Renca, San Joaquin,
San Miguel, San Ramon, Vitacura, Puente Alto, Pirque, San Jose de Maipo, Colina, Lampa,
Tiltil, San Bernardo, Buin, Calera de Tango, Paine, Melipilla, Alhue, Curacavi,
Maria Pinto, San Pedro, Talagante, El Monte, Isla de Maipo, Padre Hurtado, Penaflor.

See `data/rm_municipal_codes.json` for the exact `codigo_organismo` and the verified
`nombre_organismo` (buyer name as returned by the API) per comuna.

## Notes / caveats for future maintenance

- A few comunas have more than one municipal-adjacent organism registered (for
  example a "Corporacion Municipal de Educacion y Salud" alongside the municipality
  itself, e.g. San Bernardo, Nunoa, La Florida, La Reina, Penalolen, Colina, Lampa,
  Calera de Tango, San Joaquin). The verified codes in the output file are for the
  municipality itself (the entity that appeared in a real order's `Comprador` with a
  matching comuna/region and an `is_municipal` name), not its satellite corporations.
  Those corporations are separate legal entities with separate `CodigoOrganismo`
  values and are intentionally excluded from this file; a future phase could add them
  as additional rows if in-scope.
- If a future re-run cannot verify a comuna (no order placed on the sampled dates),
  extend `--dates` with more recent weekdays; the script is idempotent and will not
  overwrite already-verified comunas that are absent from a re-run's candidate set.
- The `BuscarComprador` directory endpoint is a convenience for finding candidates
  faster than blind by-date sampling; it is explicitly not itself treated as a source
  of truth for `codigo_organismo` per the project's hard rule that every code must be
  confirmed via a real per-order detail response.
