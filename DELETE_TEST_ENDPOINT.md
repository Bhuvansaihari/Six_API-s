# How to Delete Test Endpoint

When you're done testing, follow these steps to remove the test endpoint:

## Files to Delete

1. **`app/api/resume_test/`** - Delete the entire directory
   - `app/api/resume_test/router.py`
   - `app/api/resume_test/__init__.py`

## Code to Remove from `app/main.py`

1. **Remove the import** (around line 26):
   ```python
   # TEMPORARY TEST ENDPOINT - Can be safely deleted later
   from app.api.resume_test.router import router as resume_test_router
   ```

2. **Remove the router include** (around line 166):
   ```python
   # TEMPORARY TEST ENDPOINT - Can be safely deleted later
   app.include_router(resume_test_router)
   ```

That's it! The test endpoint is completely isolated and won't affect any other APIs.

## Test Endpoint Details

- **URL**: `POST /test/resume-parse`
- **Tag**: `test-resume-parsing` (visible in Swagger UI)
- **Purpose**: Test resume parsing without database operations
- **Returns**: Parsed JSON matching canonical schema

