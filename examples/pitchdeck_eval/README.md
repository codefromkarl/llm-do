# Pitchdeck Evaluator Example

AI-powered systematic evaluation of startup pitchdecks for investors.

This is a complete example of using `llm-do` for a real-world workflow.

## What This Shows

- **Spec-driven workflow** defined in `SPEC.md`
- **Custom toolbox** with hardened functions (`tools.py`)
- **Progressive hardening** - Started flexible, extracted `normalize_filename()`
- **Natural language commands** with flexible variations
- **Multiple workflows** - Processing, questions, re-evaluation, comparison

## Quick Start

1. **Navigate to this directory**:
   ```bash
   cd examples/pitchdeck_eval
   ```

2. **Process pitchdecks**:
   ```bash
   # Drop a PDF in pipeline/
   cp ~/Downloads/StartupDeck.pdf pipeline/

   # Process it
   llm do "process all pitchdecks in pipeline/" --toolbox tools.PitchdeckToolbox
   ```

3. **Try other commands**:
   ```bash
   llm do "list all companies in portfolio" --toolbox tools.PitchdeckToolbox
   llm do "normalize the filename 'Real Research (YC S24).pdf'" --toolbox tools.PitchdeckToolbox
   ```

4. **Model requirements**:

   This directory ships with `llm-do.toml` which requires the active llm model to support PDF attachments. If your default model does not, override it (for example `llm do ... -m claude-3.5-sonnet`) or update the config to list an approved alternative.

## Project Structure

```
pitchdeck_eval/
├── SPEC.md                # Workflow specification (main "program")
├── tools.py               # Custom toolbox with hardened functions
├── framework/
│   └── eval_pitchdeck.md # Evaluation criteria
├── portfolio/             # Evaluated companies
├── pipeline/              # Drop zone for new PDFs
├── tests/
│   └── test_normalize.py # Tests for hardened tools
└── README.md             # This file
```

## Usage Examples

### Basic Commands

```bash
# Process all PDFs in pipeline/
llm do "process all pitchdecks in pipeline/" --toolbox tools.PitchdeckToolbox

# Filter by date (natural language!)
llm do "process pitchdecks from yesterday" --toolbox tools.PitchdeckToolbox

# Generate follow-up questions
llm do "generate questions for CompanyX" --toolbox tools.PitchdeckToolbox

# Re-evaluate with updated framework
llm do "re-evaluate CompanyX" --toolbox tools.PitchdeckToolbox

# Compare companies
llm do "compare CompanyX and CompanyY" --toolbox tools.PitchdeckToolbox
```

### Shell Alias (Recommended)

Create an alias for convenience:

```bash
# Add to ~/.bashrc or ~/.zshrc
alias llm-pitch='llm do --toolbox tools.PitchdeckToolbox'

# Then use:
llm-pitch "process all pitchdecks"
llm-pitch "generate questions for CompanyX"
```

## How It Works

1. **User drops PDF** in `pipeline/`:
   ```bash
   cp ~/Downloads/StartupDeck.pdf pipeline/
   ```

2. **User runs command**:
   ```bash
   llm do "process all pitchdecks" --toolbox tools.PitchdeckToolbox
   ```

3. **LLM reads `SPEC.md`** which contains:
   - Workflow steps (find PDFs, normalize names, create dirs, evaluate, commit)
   - Tool usage instructions
   - Edge case handling

4. **LLM executes workflow**:
   - Calls `run_bash("find pipeline/ -name '*.pdf'")`
   - Calls `normalize_filename()` (hardened tool from custom toolbox)
   - Calls `run_bash()` for file operations
   - Reads PDF and framework
   - Generates evaluation
   - Calls `write_file()` to save
   - Calls `run_bash()` for git operations

5. **Result**: Structured evaluation saved in `portfolio/CompanyName/`

## Progressive Hardening Example

This project demonstrates progressive hardening:

### Phase 1: Pure Spec (Initial)

```markdown
## Workflow
1. Normalize company name from filename (remove spaces, special chars)
```

LLM figured it out each time, sometimes inconsistently.

### Phase 2: Hardened Tool (Current)

```python
# tools.py
def normalize_filename(self, filename: str) -> str:
    """Normalize filename - hardened, tested function."""
    name = filename.replace('.pdf', '').replace('.PDF', '')
    return re.sub(r'[^a-zA-Z0-9-]', '', name.replace(' ', ''))
```

```python
# tests/test_normalize.py
def test_normalize():
    assert normalize_filename("Real Research (YC S24).pdf") == "RealResearchYCS24"
```

Now consistent and tested! ✅

### Future Phases

Candidates for hardening:
- `get_pdf_metadata()` - Extract modification date
- `prepare_pitchdeck()` - File organization workflow
- `create_log_entry()` - Consistent log format

## Customization

### Evaluation Framework

Edit `framework/eval_pitchdeck.md` to match your investment criteria:
- Add sector-specific criteria
- Define scoring systems
- Set deal-breakers

### Workflow

Edit `SPEC.md` to customize:
- Processing steps
- Natural language variations
- Edge case handling
- New workflows (e.g., portfolio reports)

Changes take effect immediately - just re-run `llm do`!

### Hardened Tools

Add new hardened tools to `tools.py`:

```python
class PitchdeckToolbox(BaseToolbox):
    def get_pdf_metadata(self, path: str) -> dict:
        """Extract PDF metadata - hardened function."""
        # Your logic here
        pass
```

Add tests in `tests/`:

```python
def test_get_pdf_metadata():
    result = get_pdf_metadata("test.pdf")
    assert "date" in result
```

## Development Workflow

1. **Edit SPEC.md** - Change workflow description
2. **Test immediately** - `llm do "task"`
3. **Observe tool calls** - See what LLM does
4. **Iterate on spec** - Refine based on behavior
5. **Notice patterns** - LLM doing same thing repeatedly?
6. **Extract to tools.py** - Create hardened function
7. **Add tests** - Test the hardened function
8. **Update spec** - Reference the new tool

## Team Collaboration

This system is designed for investment teams:

1. **Shared repo** - Everyone sees same evaluations
2. **Git workflow** - Track changes, collaborate async
3. **Spec changes** - Non-programmers can edit SPEC.md
4. **Hardened tools** - Programmers extract critical logic
5. **Clear separation** - Both roles contribute effectively

## Privacy & Security

**IMPORTANT**: This system handles confidential startup information.

- Use a **private git repository**
- Consider adding `*.pdf` to `.gitignore`
- Be mindful of API data retention policies
- Review AI-generated content before sharing externally

## More Examples

### File Operations
```bash
llm do "list all companies in portfolio" --toolbox tools.PitchdeckToolbox
llm do "show me the evaluation framework" --toolbox tools.PitchdeckToolbox
llm do "what's the git status?" --toolbox tools.PitchdeckToolbox
```

### Testing Hardened Tools
```bash
llm do "normalize 'Startup Name (YC S24).pdf'" --toolbox tools.PitchdeckToolbox
# Expected: RealResearchYCS24
```

### Natural Language Variations
```bash
llm do "process yesterday's pitchdecks" --toolbox tools.PitchdeckToolbox
llm do "evaluate the urgent pitch deck" --toolbox tools.PitchdeckToolbox
llm do "what questions should we ask CompanyX about their traction?" --toolbox tools.PitchdeckToolbox
```

## License

Apache-2.0

---

**Built with llm-do: Write specs. Execute with LLM. Harden what works.**
