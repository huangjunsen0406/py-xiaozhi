#!/bin/bash
#
# generate_translations.sh - Extract and compile Qt translations
#
# This script updates .ts translation files from source code and compiles
# them into .qm files for runtime use.
#
# Usage: ./generate_translations.sh
#
# Prerequisites:
#   - pylupdate5 (Qt5 Linguist tools)
#   - lrelease (Qt5 Linguist tools)
#   - i18n/xiaozhi.pro (Qt project file for translations)
#
# Output:
#   - i18n/source/*.ts (updated translation source files)
#   - i18n/translations/*.qm (compiled translation files)

set -e  # Exit on error
set -u  # Exit on undefined variable

# Directory paths (relative to project root)
I18N_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRO_FILE="${I18N_DIR}/xiaozhi.pro"
TRANSLATIONS_DIR="${I18N_DIR}/translations"

echo "=== Qt Translation Generator ==="
echo ""

# Check for required tools
check_dependencies() {
    local missing=0
    
    if ! command -v pylupdate5 &> /dev/null; then
        echo "ERROR: pylupdate5 not found. Install Qt5 Linguist tools."
        missing=1
    fi
    
    if ! command -v lrelease &> /dev/null; then
        echo "ERROR: lrelease not found. Install Qt5 Linguist tools."
        missing=1
    fi
    
    if [ $missing -eq 1 ]; then
        exit 1
    fi
}

# Check that the .pro file exists
check_pro_file() {
    if [ ! -f "$PRO_FILE" ]; then
        echo "ERROR: $PRO_FILE not found."
        echo "Create the Qt project file first."
        exit 1
    fi
}

# Step 1: Extract/update strings into .ts files
update_ts_files() {
    echo "Step 1: Extracting strings into .ts files..."
    echo "  Running: pylupdate5 $PRO_FILE"
    
    if pylupdate5 "$PRO_FILE"; then
        echo "  SUCCESS: .ts files updated"
    else
        echo "  FAILED: pylupdate5 exited with code $?"
        exit 1
    fi
    echo ""
}

# Step 2: Compile .ts → .qm files
compile_qm_files() {
    echo "Step 2: Compiling .ts files to .qm..."
    echo "  Running: lrelease $PRO_FILE"
    
    if lrelease "$PRO_FILE"; then
        echo "  SUCCESS: .qm files compiled"
    else
        echo "  FAILED: lrelease exited with code $?"
        exit 1
    fi
    echo ""
}

# Step 3: Copy .qm files to translations directory
copy_qm_files() {
    echo "Step 3: Copying .qm files to translations directory..."
    
    # .qm files are output to source/ directory (same dir as .ts files per xiaozhi.pro)
    local qm_files=$(find "$I18N_DIR/source" -maxdepth 1 -name "*.qm" -type f 2>/dev/null)
    
    if [ -z "$qm_files" ]; then
        echo "  WARNING: No .qm files found in $I18N_DIR/source"
    else
        mkdir -p "$TRANSLATIONS_DIR"
        
        for qm_file in $qm_files; do
            cp "$qm_file" "$TRANSLATIONS_DIR/"
            echo "  Copied: $(basename "$qm_file")"
        done
        echo "  SUCCESS: .qm files copied to $TRANSLATIONS_DIR"
    fi
    echo ""
}

# Main execution
main() {
    echo "Starting translation generation..."
    echo "Project file: $PRO_FILE"
    echo ""
    
    check_dependencies
    check_pro_file
    update_ts_files
    compile_qm_files
    copy_qm_files
    
    echo "=== Translation generation complete ==="
}

main "$@"
