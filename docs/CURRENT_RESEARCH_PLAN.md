# Singapore Housing Index: reconstruction, coverage and economic validation

Consolidated: 17 October 2026. This is the single authoritative current study specification. It preserves the original 8 September 2026 economic-analysis design and explicitly incorporates later software corrections and the user-authorised single-reviewer HDB classification audit. It is not retrospectively described as a fully prospective preregistration. Original plans, intermediate revisions and earlier results are in Archive; important changes are summarised in METHODOLOGICAL_CHANGELOG.md. RESEARCH_PLAN_REVIEW.md remains missing; its absence does not block the work supported by available specifications.

## Current completion state and boundaries

Reconstruction, source-based coverage, controlled formula comparison, historical-candidate agreement, descriptive patterns/rank associations, rental/resale models and four rental sensitivity analyses have been executed. The literature resource is a structured evidence map with unresolved full texts, not a complete systematic review. The sole reviewer's completed workbook contains 30 HDB classification responses, all agreeing with the stored algorithm; seven original saved-geocoding flags have documented address-point resolutions, separate from classification agreement and unchanged frozen model inputs. This is a targeted positive-record visual audit, not nationwide accuracy, SHI validity or address-linkage validation.

No clinical cohort, individual-income/deprivation validation or adequate health-study confounding control is established. Formal author declarations and release publication remain pending. The user approved MIT and will provide final public-release approval; no specific institutional restriction requiring separate supervisor approval has been identified in the supplied materials. The user authorises upload of the complete checked package to a PRIVATE GitHub repository. The existing public scaffold must not receive unreleased files. Public visibility requires a future explicit instruction. Zenodo metadata/files are prepared only; no public deposition or DOI issuance is authorised.

## 1. Scientific question and intended claims

**How reliably can SHI be reconstructed from current public data, and how much housing-related economic information does it provide for research using residential addresses?**

Keep three meanings of validation separate:

| Domain | Evidence in this study | Interpretation limit |
| --- | --- | --- |
| Reconstruction and linkage | Computational checks, source reconciliation, historical agreement and consequential-error investigation | Agreement between sources is not proof that every physical building or unit is correctly represented. |
| Housing-related economic information | Held-out rental prediction, supporting resale analysis and descriptive household statistics | Evidence concerns represented housing and broad economic differences. |
| Individual socioeconomic circumstances and health-study adjustment | Existing literature reviewed; no new individual-level validation assumed | This study cannot establish individual income, deprivation detection, causal effects, or adequate control of socioeconomic confounding in health research. |

The health-equity contribution is practical: document when an address-based SHI is useful, which housing groups are missing, how much a building average conceals, and how researchers should handle uncertain addresses. A clinical cohort is not essential for these claims. Housing value does not establish ownership, disposable resources, mortgage debt or the circumstances of individual residents.

### Agreed scope

- Core study: public data, nationwide HDB reconstruction, one primary rental comparison, a flat-type benchmark, supporting resale evidence and explicit disadvantaged-housing coverage.
- Preserve the established index. Current reconstruction and economic modelling concern the public HDB building frame. Private/landed classifications are not inferred from unmatched addresses; legacy candidate codes remain separate and do not form a continuous economic scale with HDB scores. Any verified extension beyond this frame requires its own documented evidence.
- Start from the published notebook; no private historical files, clinical access or new recruitment are assumed.
- The completed building exercise uses one human reviewer and up to 30 purposively selected cases, with a five-column HDB classification form. Actual time spent was not collected.
- Prepare GitHub code and a versioned DOI archive. Commercial listing prices, paid Annual Values, automated valuations and environmental/image-processing analyses are outside the core economic study. Supplementary property websites, including PropertyGuru, are accepted corroboration for the completed manual housing-classification audit; their use is not a new price outcome or internal-composition validation.

## 2. Literature uptake and supporting household statistics

Produce a structured evidence map, mainly for the supplement. Search forward citations of the 2021 paper, Singapore Housing Index, housing-index and room-index, and follow earlier methods/dataset references. Use OpenAlex, PubMed/Europe PMC and supplementary scholarly searches; save queries, dates and exclusions and refresh before submission.

Deduplicate preprints and publications. Extract population, setting, SHI source/version, formula or categories, missing-address handling, analytical role, results and limitations. Distinguish use of the reconstruction method, SHI obtained elsewhere, direct individual-SES validation, clinical associations, modifications and background citations. Mark unavailable full texts. Do not pool heterogeneous health associations or interpret citation frequency as validity. The initial 37 OpenAlex records are an unscreened discovery count.

Include one concise description of income by dwelling type, preferably per household member. Identify whether income is from employment or all sources and whether households without employed members are included. Use Census/HES definitions and denominators consistently; HES 2023 provides information beyond employment income. Education and non-housing expenditure are optional descriptive additions only if readily available; separate imputed housing rent from other expenditure.

Do not test significance across a handful of published category means, equate household categories with a mixed block's mean SHI, or mix person, household and building denominators. Geographic socioeconomic comparisons are deferred unless dates, boundaries and weights can be reconciled without expanding the core study.

## 3. Sources, reconstruction and time alignment

### Rental and resale data contracts

Use **owner-declared monthly rents in approved whole-flat rental records**. HDB states that these amounts are indicative and unverified. The source has approval month, town, block, street, flat type and monthly rent; it has no unit identifier, floor area, storey or tenancy-start date. Approval month is the recorded date. [HDB rental dataset](https://data.gov.sg/datasets/d_c9f57187485a850908655db0e8cfe651/view)

Rental models will not include observed floor area or rent per square metre. Do not impute a typical flat area and label it observed. HDB resales include approximate floor area, storey range and remaining lease, allowing a separate adjusted resale benchmark. [HDB resale dataset](https://data.gov.sg/datasets/d_8b84c4ee58e3cfc0ece0d773c8ca6abc/view)

Retain otherwise identical source rows: their published values may describe different flats. Remove proven repeated downloads using frozen source-row identity and retrieval provenance, not a hash of the visible transaction fields. Distinguish source records from unique units, tenancies, households and people. Audit unusual positive amounts without automatic outcome-based trimming; exclude a source error only with documented evidence.

### Software and classification

Archive the public notebook and source descriptions with retrieval metadata and checksums. Separate acquisition, address matching, calculation, validation and export into reusable Python code; the tutorial notebook calls the same implementation. Add pagination/completeness checks, timeouts, bounded retries, rate limiting, token renewal, resumable retrieval and explicit failure statuses.

Preliminary inspection found an obsolete OneMap hostname, absent current authentication, unchecked first-result matching, broad error suppression, unreachable throttling, deprecated pandas calls, an inclusive end-date boundary, and no implemented SHI calculation or validation analysis in the shared notebook. The old HDB identifier still responded and is not a confirmed defect. Maintain an issue-to-impact table: evidence, cause, correction, affected records and analytical consequences. Runtime failures alone do not establish that the 2021 results were wrong.

Publish a versioned mapping of every source composition field to room weight, with the numerator and denominator. Use the 2021 paper's recommended studio and other-rental corrections; cap the established larger HDB categories at the specified weight. Explicitly distinguish HDB executive flats from Executive Condominiums. Unknown categories, missing counts, zero totals or unreconciled denominators yield an incomplete/invalid score with a reason, not a score calculated from only the recognised units. Retain raw inputs and document historical formula variants. [2021 methods paper](https://doi.org/10.1186/s12939-021-01554-8)

Use one physical-building record plus a separate postal crosswalk. Preserve leading zeros and multiple postal codes. A postcode mapping to several candidate buildings returns an ambiguous result; the crosswalk must not multiply transaction rows. Unmatched addresses never automatically become private housing. Keep institutional exclusions and unknown addresses outside the numeric scale; any legacy-code export is separate and clearly labelled.

### Historical provenance and recent transactions

The original paper describes a **2018 comparator**; the public Mendeley dataset describes a **2020 update**. Identify the exact public file, version, checksum and declared reference dates. Describe comparisons against that resource; do not claim to reproduce the original comparator unless its identity can be established. The selected public historical comparator is [Mendeley version 1](https://data.mendeley.com/datasets/pj3dkvskr9/1), DOI 10.17632/pj3dkvskr9.1.

Seek a suitable archived HDB composition snapshot among readily accessible sources. If unavailable, explicitly describe the analysis as a current reconstruction linked to recent historical transactions. Neither a page update date nor a displayed year range establishes a block's composition in 2024–2025. Retain source-reference and retrieval dates separately; flag transactions before recorded completion, known alterations and omitted demolished blocks. Current-source coverage is not an exhaustive historical housing inventory.

## 4. Coverage of disadvantaged housing: a main result

Use all residential HDB blocks in the frozen composition source as the coverage frame, with historical-frame limitations disclosed. Produce a main-paper coverage table showing the numbers with usable composition, usable SHI, resolved linkage, records in the study period, and eligibility for rental/resale modelling.

Report separate stages for:

- Blocks with no source rental/resale records linked in the selected period.
- Source market records with failed or ambiguous building matches; do not assign these to known blocks without evidence.
- Linked records/blocks excluded for invalid amounts, dates, scores or required covariates.
- Buildings actually represented in each analysis. Until unmatched records are resolved, absence of linked records does not prove that no transaction occurred.

Show building counts and dwelling-unit coverage where composition permits; neither measures residents covered. Descriptive breakdowns are SHI bands [1,2), [2,3), [3,4), [4,5), [5,6], a separate missing-SHI group, building age, town and rental-category composition. These display bands do not replace continuous SHI in models.

Retain the proportion of units in source rental categories as a descriptive field. Distinguish all units recorded as rental, a mix of sold and rental units, no rental units recorded, and incomplete composition. Use source-based labels; do not infer each unit's assistance scheme. Separately identify known Public Rental Scheme housing where positive evidence is available. The subsidised scheme is distinct from owner-declared whole-flat market rentals and is not another market-price validation sample. [HDB public-rental rents](https://www.hdb.gov.sg/renting-a-flat/public-rental-scheme/application-process/rents-and-deposits)

Make low-SHI, rental-category-only, newer and otherwise unrepresented blocks visible even when they cannot enter price models. Good performance among represented buildings cannot validate excluded groups; weighting observed records cannot create evidence for buildings with no observations.

## 5. Primary rental analysis and fair benchmarks

### Eligibility and target

Use approval months from 1 January 2024 through 31 December 2025: `date >= 2024-01-01` and `date < 2026-01-01`. Include every otherwise eligible building with at least one source record. Require unique linkage to an HDB residential building, a complete valid SHI, a valid positive monthly rent and required covariates. Retain excluded records in the accounting report rather than silently imputing SHI or resolving ambiguity.

The primary estimand is prediction error for an **equally weighted building with eligible rental records**. Use a common complete-case sample for the four models, including recorded flat type; describe any coverage lost by this requirement. It does not represent all dwellings, households, or buildings without rental records. No recruitment or retrospective power calculation is needed: use all eligible records and report buildings, coverage and precision.

### Four models, one primary comparison

| Model | Predictors | Role |
| --- | --- | --- |
| A | Coordinates, building age and approval month | Baseline when an address is available but individual flat type is not. |
| B | A + continuous SHI | **Primary: B versus A**, the economic information added by an address-derived SHI. |
| C | A + the rented flat's recorded type | Benchmark when individual flat type is known. |
| D | C + continuous SHI | Secondary: D versus C, additional building information beyond flat type. |

Also compare B with C descriptively. If B improves on A while D scarcely improves on C, that would support SHI's usefulness when individual flat information is unavailable, with limited additional information once flat type is known. Whether SHI performs comparably to recorded flat type depends on the separate B-versus-C comparison.

Use weighted least-squares regression on the **monthly-rent dollar scale**, avoiding back-transformation ambiguity. Default location specification: a modest tensor-product natural cubic spline of projected building coordinates, with four basis functions per coordinate; age and SHI each use a natural cubic spline with three degrees of freedom. Approval month and flat type are categorical. Calculate age at the recorded approval year using completion year, without inventing a completion month. Use identical base terms across models; estimate spline knots and all preprocessing from training data only. Use a linear term if a continuous predictor has too few distinct training values for its specified spline. No model-family competition or outcome-driven basis-size search is planned.

Coordinates, rather than town-only effects, allow local spatial adjustment and prediction in geographic holdouts without estimating an entirely unseen town category. Freeze the implemented formula, transforms and random seed before fitting comparative models. Record rank-deficiency handling and any essential specification change before viewing performance comparisons.

### Evaluation, weighting and uncertainty

- Main evaluation: five-fold cross-validation grouped by physical building, using the same folds for all models. Every source row and postal alias of a building stays together. Use seed 20260908 and retain the fold manifest. Any preprocessing or tuning is training-only.
- Fitting weights: each record receives `1 / number_of_eligible_training_records_in_its_building`, so each training building has equal total weight.
- Primary measure: first average absolute held-out dollar errors within each building, then average over buildings. Report A and B errors, improvement `MAE_A - MAE_B` in **S$ per month**, and `100 * (MAE_A - MAE_B) / MAE_A` as percentage reduction. Positive improvement means lower error; do not suppress negative findings.
- Obtain paired 95% percentile intervals from 2,000 whole-building bootstrap resamples of the held-out predictions, retaining all model predictions together. These intervals describe variation across evaluated buildings conditional on fitted models, not all model-training uncertainty. Records and the five folds are not independent repetitions.
- Secondary measure: out-of-sample R-squared from pooled held-out predictions with inverse-record-count building weights and the corresponding weighted outcome mean. It may be negative. Report D versus C in the same units and with the same paired evaluation.

A detectable improvement is not automatically useful. Assess its dollar magnitude, percentage, uncertainty and consistency without inventing a universal threshold for socioeconomic validity.

## 6. Supporting analyses and limited robustness checks

### Resales

Use registered HDB resale records for the same 2024–2025 window and repeat A versus B, with registration month replacing approval month and total resale price as the dollar outcome. This is supporting economic evidence, not a second independent demonstration of individual SES validity.

For the adjusted resale benchmark, compare location + registration month + flat type + observed approximate floor area + storey range + remaining lease, with and without SHI. Use remaining lease instead of simultaneously adding completion age and lease-start age. Use one common eligible sample for this paired comparison and report its coverage separately. Apply the same fitting/evaluation weighting and building grouping. A price-per-square-metre plot may be descriptive for resales only; do not expand this into another model-selection exercise.

Present building-level rent and resale gradients and rank associations as descriptive supporting results. Do not assume every neighbouring SHI category or every individual property must follow a monotonic ordering.

### Exactly four planned rental sensitivity checks

Run each as a single change to the primary B-versus-A analysis; do not combine them factorially or repeat them across every subgroup:

1. Use the 12 months of 2025 instead of 24 months.
2. Require at least three eligible records per building instead of one.
3. Give source records equal weight in both fitting and evaluation instead of equal building weight; retain building-grouped validation and uncertainty.
4. Use five spatial holdouts instead of ordinary building folds. Define compact geographic groups from unique-building coordinates only, using seeded five-cluster spatial grouping, and hold out each whole group. Save a map and group sizes; specify this as geographic transfer, without claiming complete independence across spatial boundaries.

Keep mixed-composition blocks as the main descriptive subgroup, defined by more than one populated room-weight category. Report within-block dispersion and held-out errors; interpret these as housing heterogeneity and economic performance, not income misclassification. Use SHI, age and town summaries mainly for coverage and descriptive variation. No broad interaction-testing programme is planned. Any additional analysis motivated by a consequential unexpected finding is labelled exploratory with its reason.

## 7. Reconstruction checks and historical agreement

- Check all counts, denominators, score bounds, building duplicates, crosswalk ambiguity and unrecognized categories. Verify the formula with independently worked examples. Incomplete composition is never labelled a complete SHI.
- Flag resale flat types absent from the matched block's composition. Consider sold-unit categories where source definitions support that comparison; otherwise document a broader mapping. Check dates, category mappings, conversions and linkage before attributing an error. No flags does not verify all unit counts. Do not infer composition from the transacting subset or silently overwrite source counts.
- For the precisely identified historical dataset, prioritise absolute differences and category changes on unique matched buildings. Add a Bland–Altman plot and a two-way mixed-effects, single-measure, absolute-agreement ICC, explicitly labelled ICC(A,1), as supporting summaries. Report paired count, mean difference and limits of agreement; limits of agreement are not confidence intervals for the mean.
- Sources may share HDB inputs and differ in vintage. Separate historical/current differences from a calculation of old and corrected formulas on the **same input and buildings**. Only that controlled formula comparison isolates formula effects; leave unresolved causes uncertain.
- The user-authorised manual exercise is a single-reviewer targeted visual audit of HDB building classification. Retain the 30 selected cases: 9 transaction/composition triggers, 1 rental-category-only case, 4 historical conflict/multiple-postal cases and 16 large remaining historical SHI differences. The form contains only Case ID, address, navigation link, Yes/No/Unable to determine and optional notes. Algorithm labels and technical evidence are separate backend files. Instructions withhold the algorithm key until completion where feasible; prior familiarity means full blinding cannot be guaranteed.
- Twenty-three links use unique exact saved OneMap address coordinates; seven use address-search fallbacks. A response does not independently attest a particular panorama, viewing angle or imagery date. The recorded 30 responses are all HDB and all agree with the algorithm. No non-HDB or indeterminate response was entered. This selected algorithm-positive sample does not establish specificity, population accuracy, correct address/postal identity, internal composition or individual SES. All seven original location flags have separate documented address-point resolutions based on retained OneMap candidates and corroborating records. Frozen model-coordinate eligibility and historical-score conflicts are unchanged; no correction is inferred from binary agreement. The reviewer confirms supplementary property websites including PropertyGuru were used when Street View was unavailable or insufficient; case-specific site-use details were not collected.
- Compare determinate answers with stored labels by stable case ID. Exclude blank and Unable responses from the agreement denominator. Save exact received workbook, hashes, coded responses and processing timestamps separately; processing time is not observation time. Preserve uncertain cases and require corroborating official evidence before any versioned derived-data correction. No source/SHI edits are applied automatically.

## 8. Manuscript, release and study boundaries

Target **International Journal for Equity in Health**, centring the manuscript on reconstruction reliability, disadvantaged-housing coverage, the primary rental comparison and supporting resale findings. Explain consequences for address-based health-equity research rather than presenting a general property-price prediction exercise. The sole current submission target is International Journal for Equity in Health. [Journal scope](https://link.springer.com/journal/12939/aims-and-scope).

Keep the formula mapping, evidence map, detailed software diagnostics and sensitivity results mainly in the supplement. Report small, null and unfavourable findings. Include a practical guide to using SHI with only addresses, using it when flat type is known, interpreting mixed/rental-category buildings, retaining missingness, and choosing a dated dataset. Include the institutional ethics and AI-use statements appropriate to the actual work; do not assume every use of public data is universally exempt.

Release one building table, a postal crosswalk, dictionary, source/version manifest, checksums, coverage and validation reports, and a worked linkage example. Include source-reference dates, retrieval dates, housing class, SHI version, composition completeness, rental-category share and quality flags. Keep known private classifications separate from claims about HDB economic validation.

Prepare GitHub documentation, tests, versioned source archives and citation information plus a Zenodo-ready archive. Creator metadata must be supplied before asserting a complete CITATION.cff/Zenodo record; no names, URLs or DOI may be invented. Reproduction uses frozen inputs; live-data refresh is a separate operation. Archive inputs where permitted and document field-specific redistribution limits and upstream attribution. Ask users to cite the 2021 paper, the new methods paper when available, and the exact dataset/software release, retaining foundational SHI references where appropriate. Attribution and citation metadata facilitate credit but cannot guarantee compliance.

Commercial listings, IRAS Annual Values and automated valuations are deferred. The Wang et al. visual-environment paper is related literature; an imagery/greenery extension belongs to a separately scoped future study with an initial coverage audit. Existing approved address-linked income or hardship data could support stronger individual-SES claims in a future extension, but no new cohort is required for this paper.

## 9. Implementation sequence and acceptance criteria

1. Archive notebook, review, source descriptions and available snapshots; identify comparator provenance and freeze the formula/model specifications.
2. Repair acquisition and calculation, reconstruct buildings/crosswalks, and produce record-accounting and disadvantaged-housing coverage reports before economic modelling.
3. Run paired formula/historical comparisons and the flat-type consistency audit; document consequential unresolved issues without forcing a decision.
4. Freeze analysis eligibility and folds, run the primary rental and flat-type comparisons, then supporting resales and the four declared sensitivity checks.
5. Complete literature/household context, manuscript and usage guidance; prepare the versioned code/data release and clean-environment reproduction.

Acceptance requires accounting for source records, an explicit excluded/unresolved population, measured defect consequences and consistent manuscript/release artifacts. Tests must cover authentication and truncated retrieval, zero and incomplete compositions, special-category mappings, ambiguous postcodes, leading zeros, aliases that must not multiply records, retention of repeated-looking source rows, proven download duplicates, date boundaries, chronology flags, building separation across folds, training-only transformations, fitting/evaluation weights, paired dollar/percentage metrics and building-level resampling. Validate the published results from frozen inputs independently of a live refresh. Statistical significance is not an acceptance criterion.

## Source register

- [Original methods paper](https://doi.org/10.1186/s12939-021-01554-8)
- [Published notebook](https://colab.research.google.com/drive/1sdWtP4e-mIkDpU6pMdGrzpNvD_RJ8bBe)
- [Public historical dataset, version 1](https://data.mendeley.com/datasets/pj3dkvskr9/1)
- [HDB property information](https://data.gov.sg/datasets/d_17f5382f26140b1fdae0ba2ef6239d2f/view)
- [HDB owner-declared whole-flat rental records](https://data.gov.sg/datasets/d_c9f57187485a850908655db0e8cfe651/view)
- [HDB registered resale records](https://data.gov.sg/datasets/d_8b84c4ee58e3cfc0ece0d773c8ca6abc/view)
- [HDB Public Rental Scheme rents](https://www.hdb.gov.sg/renting-a-flat/public-rental-scheme/application-process/rents-and-deposits)
- [OneMap API](https://www.onemap.gov.sg/apidocs/)
- [URA API](https://eservice.ura.gov.sg/maps/api/)
- [Census 2020 tables](https://www.singstat.gov.sg/publications/reference/cop2020/cop2020-sr2/census20_stat_release2)
- [HES 2023 income](https://www.singstat.gov.sg/modules/infographics/hes/household-income)
- [Household income definitions/report](https://www.singstat.gov.sg/-/media/files/publications/households/pp-s31.ashx)
- [Grouped and spatial cross-validation methods](https://doi.org/10.1111/ecog.02881)
- [Singapore Open Data Licence](https://data.gov.sg/open-data-licence)
- [International Journal for Equity in Health scope](https://link.springer.com/journal/12939/aims-and-scope)
- [Related visual-environment study, future-work context](https://doi.org/10.1088/2515-7620/ae5589)




## Frozen sources, implementation and actual deviations

The five checksum-pinned inputs are recorded in Code/frozen_inputs.json and the source/version manifest. HDB Property Information is the 8 October 2026 source snapshot retrieved 16 October 2026; rental and resale source files were retrieved 16 October 2026. The saved OneMap responses are dated 16 October 2026. Historical comparison uses Mendeley v1, DOI 10.17632/pj3dkvskr9.1, published 23 March 2021 and described as a 2020 update; its identity with the original paper's 2018 comparator is not established. The current source is not a 2024–2025 historical building census.

The implemented current room weights are 1room_sold=1, 2room_sold=2, 3room_sold=3, 4room_sold=4, 5room_sold=5, exec_sold=5, multigen_sold=6, studio_apartment_sold=1, 1room_rental=1, 2room_rental=2, 3room_rental=3 and other_room_rental=4. The historical same-input variant sets studio=3 and other_room_rental=0 in the numerator while retaining the published dwelling-total denominator. Source count reconciliation and completeness gates apply before scoring. See Code/src/shi/reconstruction.py and the dictionary for exact executable definitions.

The implemented spatial term was repaired after provisional comparative results had been inspected: a full four-by-four natural-spline tensor with training-only centring and predictor-only rank reduction replaces the insufficient interaction-only term. All models/sensitivities were rerun. Earlier results are archived. The model family, seed, periods and building-level fitting/evaluation estimands were retained. This timing is explicit, not silently rewritten as prospectively frozen.

## Current reproducibility and release acceptance

From Code run `python scripts/run_pipeline.py --profile reproducibility`. It must verify exact frozen hashes, stop on failed stages, produce reconstruction/coverage/descriptive/model/sensitivity outputs, report recorded human audit results separately and pass integrity checks. Then run the full tests, independent audit and numeric reference checks. Preserve OOF predictions, source IDs, fold manifests, source hashes and before/after comparison evidence. Equal counts are not forced to match the paper.

Only verified claims/tables/figures may enter the manuscript. Confirm supplementary records, main-text counts, recorded audit results and actual source versions agree. Release code must run outside the personal Desktop folder. MIT applies to original code; source data retain their attribution/reuse terms and exclusions. The permitted HDB/OneMap frozen-input archive is separate from Git history; the exact Mendeley source can be retrieved from its public version and verified by checksum. No account secret, image, private note or personal workbook metadata belongs in a public release.

Submission readiness additionally requires truthful author/affiliation/declaration/AI-use/cover-letter facts and actual verified public code/data identifiers after explicit user publication approval. The historical reference-period uncertainty, frozen-coordinate coverage limitations and incomplete literature screening remain disclosed. The Mendeley v1 comparator is approved for this study; recovery of the original 2018 dataset is not an outstanding task. All seven original targeted location flags now have documented resolutions. Author declarations remain square-bracket placeholders for manual editing. Private upload is authorised; public release and Zenodo publication remain withheld.


## Final decisions on 17 October 2026

The selected Mendeley public historical SHI dataset is the comparator for this study. Do not continue original-2018 recovery or require approval for comparator inclusion. Its 2021 publication date differs from the declared 2020 update and the CSV has no explicit reference-date column. The completed single-reviewer classification records are valid with supplementary property-site evidence. Technical address-point review resolves all seven original flags without rewriting frozen model inputs. All author-declaration and AI/cover-letter placeholders remain for the user. MIT applies to original code; independent source terms remain. Upload the checked package to a PRIVATE repository only; prepare Zenodo locally without public deposition.
