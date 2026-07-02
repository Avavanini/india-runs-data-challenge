# Redrob Candidate Ranker — founding-recruiters

This repository contains the candidate discovery and ranking system for the **Redrob Hackathon**. Our team, **founding-recruiters**, has designed a high-performance, rule-based candidate ranker that screens out honeypots/anomalies and identifies the top 100 candidates based on job description fit.

## Repository Structure

- [rank.py](file:///rank.py): The main candidate ranker PoC script.
- [validate_submission.py](file:///validate_submission.py): Validates the format and constraints of the submission CSV.
- [submission_metadata.yaml](file:///submission_metadata.yaml): Metadata including team information and repository setup.
- [submission.csv](file:///submission.csv): The generated top 100 candidate ranking CSV.
- [requirements.txt](file:///requirements.txt): File specifying dependencies (none needed, built with standard library).

## How to Reproduce

To generate the submission CSV, execute the following command:

```bash
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
```

### Validation

To validate the generated `submission.csv` against format constraints and business rules, run:

```bash
python validate_submission.py submission.csv
```

## Methodology Summary

Our ranker implements a robust scoring and filtering architecture:
1. **Disqualification Filters**:
   - **Honeypot Screening**: Rejects candidates with impossible profile patterns (e.g., expert skill with 0 duration, job duration exceeding overall experience, or experience vs. career span mismatch).
   - **Location Filtering**: Relocation-unwilling candidates outside of India are filtered.
   - **IT Services Check**: Disqualifies candidates whose entire profile history consists only of major IT services firms to focus on product-oriented backgrounds.
2. **Scoring Components**:
   - **Experience (YoE)**: Optimal scoring for 6.0 to 8.5 years of experience.
   - **Job Title Match**: High weight for roles matching AI, ML, Recommendation, and Search Engineers.
   - **Skill Match**: Weighted scores for retrieval skills (vector databases, RAG, search relevancy, PyTorch, Python, etc.) with a multiplier for proficiency level.
   - **Career History Mining**: Text scan of career history for search/retrieval keywords.
   - **Education Tier**: Multipliers based on university tier.
3. **Behavioral Multipliers**:
   - Scores are adjusted dynamically by recruiters' response rates, active statuses, notice periods, and interview completion flags to maximize outreach conversion.
