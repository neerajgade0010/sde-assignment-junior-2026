# AI Usage Disclosure

## AI Tool Used

ChatGPT (OpenAI)

## How AI Was Used

AI assistance was used during the development of this assignment for the following purposes:

1. **Understanding requirements:** Helped interpret the assignment requirements and break the work into manageable implementation steps.

2. **Implementation guidance:** Assisted with designing and implementing Python modules for lead ingestion, event ingestion, data validation, schema loading, database operations, and report generation.

3. **Data security:** Provided guidance on implementing PII encryption and deterministic phone-number hashing.

4. **Debugging:** Helped investigate and resolve implementation issues encountered during development, including timestamp handling, data normalization, and ingestion behaviour.

5. **Testing:** Assisted in preparing unit tests and interpreting test results.

6. **Documentation:** Assisted in preparing the submission documentation and explaining setup and execution steps.

## Human Review and Verification

AI-generated suggestions and code were reviewed and tested during development.

The implementation was run against the provided data drops. The generated reports were inspected, and the automated test suite was executed.

The final implementation and submitted files remain the responsibility of the author.

## Verification

The project test suite was executed using:

```powershell
python -m pytest -v
```

The test run completed with 33 passing tests.