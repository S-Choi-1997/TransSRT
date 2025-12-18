# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A collection of Python utilities for processing SRT (SubRip subtitle) files. The scripts handle format correction and token counting for subtitle content.

## Scripts

### fix_srt.py
Converts malformed SRT files where entries are on single lines (number + timestamp + text separated by spaces) into proper SRT format with each component on separate lines.

**Usage:**
```bash
python fix_srt.py
```

Modify `input_file` and `output_file` variables in the `__main__` block to process different files.

### count_tokens.py
Extracts subtitle text content (excluding timestamps and numbering) from SRT files and calculates token count using tiktoken.

**Requirements:**
```bash
pip install tiktoken
```

**Usage:**
```bash
python count_tokens.py
```

Modify `srt_file` variable in the `__main__` block to analyze different files.

## SRT Format

Both scripts use the same regex pattern to parse SRT entries:
- Pattern: `(\d+)\s+(\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3})\s+(.+?)(?=\n\d+\s+\d{2}:|\Z)`
- This handles malformed single-line entries common in this project

Proper SRT format should be:
```
[number]
[timestamp]
[subtitle text]
[blank line]
```
