# Resume Filename Change Summary

## Change Made

Updated the Resume Intake API to store resume filenames using the **candidate's name** instead of temporary filenames.

## Before vs After

### Before
```
resume_file_name: tmpw4k6gujb.pdf
```

### After
```
resume_file_name: John_Doe.pdf
```

## How It Works

The code now:

1. **Extracts candidate name** from the parsed resume data
2. **Sanitizes the name** (removes special characters, replaces spaces with underscores)
3. **Creates filename** in format: `FirstName_LastName.pdf`
4. **Stores in database** with the new filename

## Examples

| Candidate Name | Generated Filename |
|----------------|-------------------|
| John Doe | `John_Doe.pdf` |
| María García | `Mara_Garca.pdf` |
| Robert Smith Jr. | `Robert_Smith_Jr.pdf` |
| 李明 (Li Ming) | `candidate_3044.pdf` (fallback) |
| (No name) | `candidate_3044.pdf` (fallback) |

## Filename Sanitization

The code removes/replaces:
- ✅ Special characters (only keeps alphanumeric, spaces, hyphens, underscores)
- ✅ Spaces → Underscores
- ✅ Accented characters → Removed (for filesystem compatibility)

## Fallback Logic

If candidate name is not available:
1. Uses `first_name` only if `last_name` is missing
2. Uses `last_name` only if `first_name` is missing
3. Uses `candidate_{cand_id}` if both are missing (e.g., `candidate_3044.pdf`)

## File Location

**Modified**: [`app/services/resume_intake/database.py` (lines 179-219)](file:///c:/Users/Bhuvansai%20Hari/Auto_apply-CandidateSync-Merged---Clean-/app/services/resume_intake/database.py#L179-L219)

## Testing

Upload a resume and check the database:

```sql
SELECT cand_id, first_name, last_name, resume_file_name 
FROM auto_apply_cand 
WHERE cand_id = 3044;
```

Expected result:
```
cand_id | first_name | last_name | resume_file_name
--------|------------|-----------|------------------
3044    | John       | Doe       | John_Doe.pdf
```

## Note

- The **actual file on disk** still has the temporary name (e.g., `tmpw4k6gujb.pdf`)
- Only the **database field** `resume_file_name` uses the candidate name
- The `resume_storage_path` still points to the original temporary file

This is intentional to avoid file system conflicts if multiple candidates have the same name.

## Logging

New log message added:
```
INFO | Resume filename set to: John_Doe.pdf for candidate_id=3044
```

✅ Change is complete and ready to use!
