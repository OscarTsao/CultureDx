# 6. Analysis

## 6.1 Error Analysis

- Most common misclassification patterns
- Confusion between closely related disorders (F32 vs F33, F41.0 vs F41.1)
- Impact of transcript length on accuracy

## 6.2 Somatization Impact

- Performance delta with/without somatization mapping
- Coverage analysis: what fraction of Chinese symptoms require somatization mapping
- Case studies: diagnoses changed by somatization normalization
- Examples:
  - Patient presenting with "胸闷, 心慌" (chest tightness, palpitations) → mapped to F41.1 GAD somatic criteria
  - Patient reporting "浑身没劲, 吃不下饭" (whole body weakness, can't eat) → mapped to F32 somatic features

## 6.3 Evidence Quality

- Criterion coverage: what fraction of ICD-10 criteria have supporting evidence
- Evidence precision: false positive rate in evidence extraction
- Retrieval effectiveness: dense vs sparse vs hybrid
- Negation detection impact on evidence accuracy

## 6.4 Failure Modes and Abstention

- When does the system abstain? Analysis of abstention patterns
- False abstention rate (system abstains when correct diagnosis was possible)
- Triage cascade failures (HiED misroutes, PsyCoT catches)
- Calibrator confidence distribution analysis

## 6.5 Teacher-Student Gap

- Qwen3-32B-AWQ (teacher) vs Qwen3-8B-SFT (student) performance comparison
- Quality of teacher-generated training data
- Where does the student model fall short?

<!-- TODO: Write full analysis with figures and concrete examples -->
