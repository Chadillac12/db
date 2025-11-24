"""Reorganize markdown exports into hierarchical folder structure by section numbers.

This script takes the flat markdown export from build_requirements_db_v2.py and creates
a hierarchical copy where files are organized into folders based on their section numbers.

Example structure:
  Flat:        FCSS/FCSS-00123.md
  Hierarchical: FCSS/4/4.1/4.1.2/FCSS-00123.md
"""

import argparse
import re
import shutil
from pathlib import Path
from typing import Optional, Tuple


def parse_section_number(section: str) -> Optional[list[str]]:
    """Parse a section number into its hierarchical components.
    
    Args:
        section: Section number string like "4.1.2" or "4.1.2-1"
        
    Returns:
        List of section components ["4", "4.1", "4.1.2"] or None if invalid
        
    Examples:
        "4.1.2" -> ["4", "4.1", "4.1.2"]
        "1.2.3-5" -> ["1", "1.2", "1.2.3"]  (ignores suffix after dash)
        "5" -> ["5"]
        "" -> None
    """
    if not section:
        return None
    
    # Remove suffix after dash (e.g., "4.1.2-1" -> "4.1.2")
    section_base = section.split('-')[0].strip()
    if not section_base:
        return None
    
    # Split by period
    parts = section_base.split('.')
    
    # Build hierarchical path components
    components = []
    for i in range(len(parts)):
        components.append('.'.join(parts[:i+1]))
    
    return components


def extract_section_from_yaml(file_path: Path) -> Optional[str]:
    """Extract section number from YAML frontmatter.
    
    Tries multiple fields in order:
    1. Section_Number
    2. Section
    3. Object_Number (if it looks like a section)
    4. SRS_Section (for SRS documents)
    
    Args:
        file_path: Path to markdown file
        
    Returns:
        Section number string or None
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        
        # Extract YAML frontmatter
        yaml_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if not yaml_match:
            return None
        
        yaml_content = yaml_match.group(1)
        
        # Try different field names in priority order
        field_patterns = [
            r'Section_Number:\s*"?([^"\n]+)"?',
            r'Section:\s*"?([^"\n]+)"?',
            r'Object_Number:\s*"?([^"\n]+)"?',
            r'SRS_Section:\s*"?([^"\n]+)"?'
        ]
        
        for pattern in field_patterns:
            match = re.search(pattern, yaml_content)
            if match:
                section = match.group(1).strip()
                # Only use Object_Number if it doesn't contain a dash
                # (section headers, not requirements)
                if 'Object_Number' in pattern and '-' in section:
                    continue
                if section and section.lower() not in ('none', 'null', ''):
                    return section
        
        return None
    except Exception as e:
        print(f"Warning: Error reading {file_path}: {e}")
        return None


def create_hierarchical_path(base_dir: Path, doc_folder: str, section: str) -> Path:
    """Create hierarchical folder path based on section number.
    
    Args:
        base_dir: Base output directory
        doc_folder: Document type folder (e.g., "FCSS")
        section: Section number (e.g., "4.1.2")
        
    Returns:
        Full hierarchical path (e.g., base_dir/FCSS/4/4.1/4.1.2/)
    """
    components = parse_section_number(section)
    
    if not components:
        # No section - put in _unsectioned folder
        return base_dir / doc_folder / "_unsectioned"
    
    # Build path: base_dir/FCSS/4/4.1/4.1.2/
    path = base_dir / doc_folder
    for component in components:
        # Sanitize folder name (remove any problematic characters)
        safe_name = re.sub(r'[<>:"|?*]', '_', component)
        path = path / safe_name
    
    return path


def reorganize_markdown_exports(
    source_dir: Path,
    output_dir: Path,
    dry_run: bool = False,
    verbose: bool = False
) -> Tuple[int, int, int]:
    """Reorganize markdown files into hierarchical structure.
    
    Args:
        source_dir: Source directory with flat markdown exports
        output_dir: Output directory for hierarchical structure
        dry_run: If True, only show what would be done
        verbose: If True, print detailed progress
        
    Returns:
        Tuple of (total_files, organized_files, unsectioned_files)
    """
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")
    
    total_files = 0
    organized_files = 0
    unsectioned_files = 0
    
    # Find all markdown files in source directory
    md_files = list(source_dir.rglob("*.md"))
    
    print(f"Found {len(md_files)} markdown files in {source_dir}")
    
    for md_file in md_files:
        total_files += 1
        
        # Get relative path from source_dir to determine document folder
        rel_path = md_file.relative_to(source_dir)
        doc_folder = rel_path.parts[0] if len(rel_path.parts) > 1 else "Unknown"
        
        # Extract section number
        section = extract_section_from_yaml(md_file)
        
        if section:
            # Create hierarchical path
            target_dir = create_hierarchical_path(output_dir, doc_folder, section)
            organized_files += 1
            
            if verbose:
                print(f"  {md_file.name} -> {target_dir.relative_to(output_dir)}")
        else:
            # No section - put in unsectioned folder
            target_dir = output_dir / doc_folder / "_unsectioned"
            unsectioned_files += 1
            
            if verbose:
                print(f"  {md_file.name} -> {target_dir.relative_to(output_dir)} (no section)")
        
        if not dry_run:
            # Create target directory
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            target_file = target_dir / md_file.name
            shutil.copy2(md_file, target_file)
    
    return total_files, organized_files, unsectioned_files


def main():
    parser = argparse.ArgumentParser(
        description="Reorganize markdown requirements into hierarchical folder structure by section numbers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Reorganize existing export
  python reorganize_hierarchical.py output/anythingllm_md_export output/anythingllm_md_export_hierarchical

  # Dry run to see what would happen
  python reorganize_hierarchical.py output/anythingllm_md_export output/hierarchical --dry-run -v

  # From default export location
  python reorganize_hierarchical.py anythingllm_md_export hierarchical_export
        """
    )
    
    parser.add_argument(
        "source_dir",
        type=Path,
        help="Source directory containing flat markdown exports"
    )
    
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Output directory for hierarchical structure"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually copying files"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print detailed progress information"
    )
    
    args = parser.parse_args()
    
    # Validate paths
    if not args.source_dir.exists():
        print(f"Error: Source directory does not exist: {args.source_dir}")
        return 1
    
    if args.output_dir.exists() and not args.dry_run:
        response = input(f"Output directory {args.output_dir} already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return 0
    
    print(f"\nReorganizing markdown files...")
    print(f"  Source: {args.source_dir}")
    print(f"  Output: {args.output_dir}")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()
    
    try:
        total, organized, unsectioned = reorganize_markdown_exports(
            args.source_dir,
            args.output_dir,
            dry_run=args.dry_run,
            verbose=args.verbose
        )
        
        print(f"\n{'Would process' if args.dry_run else 'Processed'} {total} files:")
        print(f"  ✓ Organized into hierarchical folders: {organized}")
        print(f"  ⚠ No section number (in _unsectioned): {unsectioned}")
        
        if not args.dry_run:
            print(f"\n✅ Hierarchical export created at: {args.output_dir}")
        else:
            print(f"\n💡 Run without --dry-run to actually create the files")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
