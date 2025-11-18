# Pipeline Directory

Drop new pitchdeck PDFs here for evaluation.

## Usage

1. **Add pitchdecks**:
   ```bash
   cp ~/Downloads/StartupName-Deck.pdf pipeline/
   ```

2. **Tell Claude to process**:
   ```
   Process all pitchdecks in pipeline/ in parallel
   ```

3. **Pitchdecks are automatically moved** to `portfolio/[CompanyName]/` after processing

## File Naming

- Name files clearly: `CompanyName-Deck.pdf` or `CompanyName-Investment-Proposal.pdf`
- The company name will be extracted from the filename
- Special characters and spaces will be normalized

## What Happens

1. AI detects PDFs in this directory
2. Extracts company name from filename
3. Creates `portfolio/CompanyName/` directory
4. Moves PDF there with normalized name
5. Evaluates in parallel with other pitchdecks
6. This directory becomes empty again

## Notes

- This directory should normally be empty (pitchdecks move to portfolio/)
- Multiple pitchdecks processed in parallel (~10 min total regardless of quantity)
- Original filenames are preserved (just normalized)
