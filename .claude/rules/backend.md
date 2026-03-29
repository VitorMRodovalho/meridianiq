---
paths:
  - "src/**/*.py"
  - "tests/**/*.py"
---

# Python Backend Rules

- Type hints required on all public functions (mypy strict)
- Pydantic v2: use `model_config = ConfigDict(from_attributes=True)`, `model_dump()` not `.dict()`
- API responses use Pydantic response models defined in `src/api/schemas.py`
- Error responses: raise `HTTPException(status_code=..., detail="...")`
- Database access only through `src/database/store.py` abstraction
- No raw SQL — all queries through Supabase client
- Analysis engines in `src/analytics/` must be stateless — receive data, return results
- Every analysis function must cite the standard it implements in its docstring
- Tests follow AAA pattern (Arrange, Act, Assert) in `tests/` mirroring `src/` structure
- No `print()` — use structured logging if needed
- Line length: 100 (configured in pyproject.toml)
