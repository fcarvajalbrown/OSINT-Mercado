# Deterministic overprice methods used by public auditors

Research note for OSINT-Mercado. The question: is there a published, deterministic formula that
turns a purchase line into an overprice estimate without a person reviewing each case? Sources
were read in full; nothing here is decided.

## What exists

### CGU Brazil, ALICE-Sobrepreço (2025)

Muniz, Montenegro, Honorato, Ihida and Luz Junnior, "Inovações na análise de preços do sistema
ALICE: Ferramenta de pesquisa automatizada e alerta de sobrepreço", Cadernos Técnicos da CGU,
ISSN 2764-6017, pp. 17-24. PDF: https://revista.cgu.gov.br/Cadernos_CGU/article/download/868/545/5698

1. Collect prices paid by the public administration for the same catalogue code (CATMAT), over a
   chosen number of months and a chosen region.
2. First filter: drop every price outside mean ± 1 standard deviation.
3. Second filter: recompute mean and standard deviation on what remains and drop again outside
   mean ± 1 standard deviation.
4. Reference price: the mean if the coefficient of variation of the remaining prices is 25% or
   less, the median if it is above 25%. The 25% cut comes from TCU, Acórdão 9603/2023, Primeira
   Câmara.
5. Alert when the price under review is above the reference.

Worked example in the paper: prices 10, 12, 13, 15, 16, 18, 20, 50, 90. Pass one drops 90, pass
two drops 50, CV 21.71%, reference = mean = 14.86.

One step is not deterministic: before the calculation an auditor marks each collected purchase as
compatible or not with the item under review (column N, "sim"/"não"). The alert is described as
"para verificação e análise".

### UFMG, Silva et al. (2024)

Silva, Costa, Gomide, Bezerra, Oliveira, Brandão, Lacerda and Pappa, "Overpricing Analysis in
Brazilian Public Bidding Items", Journal on Interactive Systems 15(1), DOI 10.5753/jis.2024.3831.
https://journals-sol.sbc.org.br/index.php/jis/article/view/3831

- Grouping replaces the auditor's compatibility step: descriptions are cleaned (special
  characters, stopwords, spelling, lemmas), split into products and services, and grouped by the
  standardized description plus district, year and month.
- Four price levels per group: normal (up to Q3), high (between Q3 and Q3 + 1.5 IQR), overpricing
  (above Q3 + 1.5 IQR), anomaly (above 100 x (Q3 + 1.5 IQR), treated as a likely data error).
- Validation against the ANP fuel maximum prices for Minas Gerais used only groups of ten or
  more prices.
- The authors state the method is not an absolute detector; a flagged price needs further
  analysis to tell justified from irregular.

### UFSC, Soares, da Silva, Zibetti and Werner (2024)

"Sobrepreço em compras públicas: Metodologia baseada na identificação de valores discrepantes",
SBBD 2024 companion proceedings, pp. 266-272, DOI 10.5753/sbbd_estendido.2024.244291.
https://sol.sbc.org.br/index.php/sbbd_estendido/article/view/30804

- Pre-filter: drop prices outside median ± 10 MAD as probable registration errors.
- M1: Tukey fence Q3 + 1.5 IQR on unit prices grouped by year.
- M2 and M3: fit an OLS price model on covariates (year, IPCA, oil price for gasoline) and flag
  standardized residuals beyond 3 (M2) or beyond the Tukey fence of the residuals (M3). Modelling
  first changes which items are flagged, because prices drift within a year.
- Flagged cases go to the Santa Catarina prosecutors' technical team.

### Not found

- The Open Contracting Partnership's 2024 red-flags guide has no unit-price-against-reference
  indicator; its Cardinal library uses the Q3 + 1.5 IQR fence on bid-level ratios.
- No published Chilean (ChileCompra, Dipres, Contraloría) method for computing sobreprecio from
  purchase orders was found.

## What this means for the project

- Deterministic pieces with an institutional source exist for every step except one: deciding
  which purchases are comparable. CGU leaves it to an auditor; UFMG replaces it with text grouping
  plus place and time.
- None of the three presents its output as a confirmed overpricing. Each calls it an alert or a
  suspicion for further analysis.
- The project's peer engine (ADR 0018, median and MAD) is already in this family; the Convenio
  Marco engine compares against the catalogue price for the same product.
