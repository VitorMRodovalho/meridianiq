Analyze and fix GitHub issue: $ARGUMENTS

1. Use `gh issue view $ARGUMENTS` to get full issue details
2. Search the codebase for relevant files mentioned in the issue
3. Read and understand the affected code
4. Implement the fix following project patterns
5. Write tests that verify the fix
6. Run `python -m pytest tests/ -q` to verify all tests pass
7. Create a descriptive commit referencing the issue number
