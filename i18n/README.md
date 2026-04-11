# py-xiaozhi Internationalization (i18n)

This directory contains the localization infrastructure for py-xiaozhi using the Qt Linguist approach.

## Directory Structure

```
i18n/
├── source/      # .ts (Translation Source) files - the master translation files
├── translations/ # Compiled .qm (Qt Message) files - ready for use
├── build/       # Temporary build artifacts during compilation
└── README.md    # This file
```

## Workflow

1. **Source files** (.ts) are created/updated in `source/`
2. **Translations** are added using Qt Linguist tools
3. **Build** step compiles .ts → .qm files into `translations/`
4. **Runtime** application loads .qm files from `translations/`

## File Types

- **.ts** - Translation Source: XML format, editable in Qt Linguist
- **.qm** - Qt Message: Binary format, optimized for runtime loading

## Notes

- Only infrastructure is set up - no translation files exist yet
- Translation files will be added in subsequent tasks
