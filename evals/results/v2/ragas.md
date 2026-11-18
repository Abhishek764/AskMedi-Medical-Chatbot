# Ragas evaluation

Golden set `v2_hard.jsonl`, 47 questions (retrieval only). Judge: none (ID metrics only). 433.9 s.

| Metric | Score | Rows |
|---|---|---|
| ID context recall | 0.872 | 47 |
| ID context precision | 0.296 | 47 |
| Faithfulness (judge) | — | 0 |
| Context relevance (judge) | — | 0 |

## Misses (expected document not retrieved)

- `v2h002` signs of sugar disease in adults — expected ['medlineplus:diabetes-type-2', 'medlineplus:diabetes'], got ['medlineplus:diabetes-type-1', 'medlineplus:hypoglycemia', 'medlineplus:hyperglycemia']
- `v2h013` low hemoglobin causes — expected ['medlineplus:anemia', 'medlineplus:iron'], got ['pmc:PMC10138976', 'pmc:PMC13466916', 'medlineplus:anemia']
- `v2h022` sunshine vitamin deficiency — expected ['medlineplus:vitamin-d'], got ['pmc:PMC11242131', 'medlineplus:vitamin-d-deficiency', 'pmc:PMC8067314']
- `v2h032` who should get the seasonal influenza shot — expected ['medlineplus:flu'], got ['pmc:PMC10176301', 'pmc:PMC6165116']
- `v2h036` side effects of crocin — expected ['openfda-otc:acetaminophen', 'openfda:00c121ff-141d-410b-8632-c884a3909552'], got ['pmc:PMC6454763', 'openfda:08d0a109-3307-47b5-8ff2-c0ad83e66f08', 'openfda:1f53de80-efc8-4930-b3e3-fba0d026af05']
- `v2h037` is dolo 650 safe with alcohol — expected ['openfda-otc:acetaminophen', 'openfda:00c121ff-141d-410b-8632-c884a3909552'], got ['pmc:PMC6454763', 'openfda:08d0a109-3307-47b5-8ff2-c0ad83e66f08', 'openfda:1d3a45f3-3854-4d0c-9241-770aa24063fd']
- `v2h042` brufen should it be taken with food — expected ['openfda-otc:ibuprofen', 'openfda:01f8fe3a-8810-4b38-8860-d95e05d37709'], got ['openfda-otc:ibuprofen', 'openfda:178dc379-e2b8-4b47-9f0c-3fc7fb435c36', 'openfda:312cd403-b211-64ef-e063-6394a90aab88']
