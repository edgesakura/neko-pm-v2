# Coding Style

## Immutability (CRITICAL)

ALWAYS create new objects, NEVER mutate:

```javascript
// WRONG
user.name = name

// CORRECT
return { ...user, name }
```

## File Organization

- Many small files > few large files
- 200-400 lines typical, 800 max
- Organize by feature/domain, not by type

## Input Validation

Validate user input at system boundaries (Zod recommended).
