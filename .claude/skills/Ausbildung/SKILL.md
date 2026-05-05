```markdown
# Ausbildung Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill introduces the core development patterns and workflows used in the Ausbildung Python codebase. It covers coding conventions, database modeling, migration workflows, and testing practices. The repository is organized for clarity and maintainability, with a focus on structured model definitions and database schema evolution.

## Coding Conventions

**File Naming**
- Use `camelCase` for filenames.
  - Example: `userProfile.py`, `databaseUtils.py`

**Import Style**
- Prefer **relative imports** within packages.
  - Example:
    ```python
    from .models import User
    from ..constants import DEFAULT_ROLE
    ```

**Export Style**
- Use **named exports** by explicitly listing symbols in `__init__.py`.
  - Example (`jyry/db/__init__.py`):
    ```python
    from .models import User, Group
    from .enums import UserRole

    __all__ = ["User", "Group", "UserRole"]
    ```

**Commit Patterns**
- Commit messages are freeform, typically around 42 characters.
  - Example: `Add support for new user roles`

## Workflows

### Add New Database Model
**Trigger:** When introducing new data entities to the application  
**Command:** `/new-model`

1. **Edit or create model classes** in `jyry/db/models.py`.
    ```python
    class Course(Base):
        __tablename__ = "courses"
        id = Column(Integer, primary_key=True)
        name = Column(String, nullable=False)
    ```
2. **Update or add enums** in `jyry/db/enums.py` if needed.
    ```python
    from enum import Enum

    class CourseType(Enum):
        ONLINE = "online"
        OFFLINE = "offline"
    ```
3. **Add or update reference constants** in `jyry/constants.py` if applicable.
    ```python
    DEFAULT_COURSE_TYPE = "online"
    ```
4. **Update mixins or base classes** in `jyry/db/base.py` if new conventions are required.
5. **Expose new models** in `jyry/db/__init__.py` by adding them to `__all__`.

### Database Migration Workflow
**Trigger:** When ORM models are modified or added, and the database schema must be updated  
**Command:** `/new-migration`

1. **Edit `alembic/env.py`** to ensure new models are imported and registered.
    ```python
    from jyry.db.models import Course  # newly added model
    ```
2. **Create or update migration scripts** in `alembic/versions/`.
    - Generate a migration script (e.g., using Alembic CLI):
      ```
      alembic revision --autogenerate -m "Add Course model"
      ```
3. **Update Alembic configuration** in `alembic.ini` or templates in `alembic/script.py.mako` if needed.
4. **Document migration usage or changes** in `alembic/README.md`.

## Testing Patterns

- **Test Framework:** Unknown (not detected)
- **Test File Pattern:** Files named with `*.test.*`
  - Example: `userModel.test.py`, `dbUtils.test.py`
- **General Practice:** Place tests alongside or near the code they test, following the naming pattern for easy discovery.

## Commands

| Command        | Purpose                                                         |
|----------------|-----------------------------------------------------------------|
| /new-model     | Start the process to add a new database model                   |
| /new-migration | Begin a new database migration after model changes              |
```
