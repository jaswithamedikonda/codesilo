# CodeSilo

CodeSilo is a local-first knowledge-silo analysis tool for Git repositories.  
It helps engineering teams identify files where contribution history suggests
concentrated ownership and limited contributor coverage.

## Why CodeSilo?

CodeSilo analyzes a repository locally. A user provides a local repository
path, and the application runs Git commands on that machine to read structured
commit and file-change history.

The core workflow does not upload source code or require a cloud token. This
makes CodeSilo suitable for teams working with proprietary or client code where
minimizing external data exposure is important.

## What it does

- Analyzes a local Git repository’s commit and file-change history
- Calculates per-file contributor activity and ownership concentration
- Distinguishes total contributors from meaningful contributors using a
  configurable activity-share threshold
- Flags potentially important paths using configured path keywords
- Presents repository-level ownership recommendations
- Lets users filter files by risk and search by file path
- Opens a file detail page with ownership evidence and a recommended action
- Preserves an analysis-run history so repeated analyses remain separate

## How ownership is assessed

For each file, CodeSilo calculates each contributor’s share of the file’s
total recorded change activity:

[
\text{Activity share} =
\frac{\text{Contributor activity}}{\text{Total file activity}} \times 100
]

A contributor is considered meaningful when their activity share is at least
10%, the current configurable threshold.

These results are ownership-risk signals based on Git history. They do not
prove that a contributor is currently available, nor do they prove that a file
is poorly maintained.

## Tech stack

- Python
- Flask
- SQLite
- Git command-line integration
- HTML, CSS, and Jinja templates

## Getting started

### Prerequisites

- Python 3.10 or newer
- Git installed and available in the terminal

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run CodeSilo

```bash
python web/app.py
```

Then open this address in your browser:

http://127.0.0.1:5000

## How to use CodeSilo

1. Open the Home page.
2. Enter the path to a local Git repository.
3. Select **Analyze repository**.
4. View the dashboard, filter files by risk, and open a file for details.

You can also analyze one of the included public sample repositories. The first
time a sample is selected, CodeSilo clones it locally.

## Privacy

CodeSilo’s local-first workflow is intended to keep the analyzed repository on
the developer’s machine.

Remote Git URL support is a potential future integration. If implemented, it
should use narrowly scoped, read-only authorization and clear data-retention
controls.

## Project status

This is a portfolio project focused on demonstrating:

- Local Git-history analysis
- Ownership-risk signal calculation
- Practical dashboard design
- Analysis-run tracking
- File-level decision support