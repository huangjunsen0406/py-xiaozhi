# Translator Guide

This guide helps you add new languages or update existing translations.

## How to Add a New Language

1. Open `i18n/xiaozhi.pro` and add a new LANGUAGES entry, for example:

```
LANGUAGES = zh_CN en_US ja_JP  # add your new language code
```

Or simply create a new `.ts` file in `i18n/source/` based on an existing one.

2. Copy an existing translation file as a template:

```bash
cp i18n/source/xiaozhi_en.ts i18n/source/xiaozhi_xx.ts
```

3. Edit the new `.ts` file and fill in your translations for each `<translation>` element.

4. Extract strings from source code:

```bash
pylupdate5 i18n/xiaozhi.pro
```

5. Compile to binary format:

```bash
lrelease i18n/xiaozhi.pro
```

The compiled file appears in `i18n/translations/`.

## How to Update Translations After Code Changes

1. Edit the source files to add or modify Chinese strings.

2. Re-run pylupdate to extract new strings:

```bash
pylupdate5 i18n/xiaozhi.pro
```

This updates all `.ts` files. Existing translations are preserved, but new strings appear with `<translation type="unfinished">` for you to fill in.

3. Edit the relevant `.ts` file(s) and provide translations for unfinished strings.

4. Recompile:

```bash
lrelease i18n/xiaozhi.pro
```

## Build Commands

```bash
cd i18n
./generate_translations.sh   # Unix (extract + compile)
```

Or manually:

```bash
pylupdate5 xiaozhi.pro      # Extract strings from source
lrelease xiaozhi.pro        # Compile .ts to .qm binary
```

## Translation Guidelines

- Preserve placeholders exactly: `%1`, `%2`, `{variable}`, etc. These are replaced at runtime.
- Match the punctuation style of the target language.
- Use context comments like `<!-- lupdate-context: ... -->` to clarify where a string appears.
- Technical terms like "MAC地址" usually should not be translated unless an established translation exists in your language.

## File Locations

| Purpose | Path |
|---------|------|
| Source translation files | `i18n/source/xiaozhi_*.ts` |
| Compiled binary files | `i18n/translations/xiaozhi_*.qm` |
| Project configuration | `i18n/xiaozhi.pro` |
| Build script | `i18n/generate_translations.sh` |
