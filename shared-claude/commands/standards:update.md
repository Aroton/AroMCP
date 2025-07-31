# Update Coding Standard

**Command**: `standards:update`

**Description**: Interactively update an existing coding standard, ensuring consistency with the template and preserving custom content.

## Usage

```bash
# Update a standard interactively
claude standards:update api-validation

# Update with specific section focus
claude standards:update api-validation --section=examples

# Update all standards that need refreshing
claude standards:update --all --check-template
```

## Process Overview

I'll help you update an existing standard by:
1. Loading the current standard and detecting what needs updating
2. Comparing against the template at `~/.claude/templates/code-standards-template.md`
3. Asking clarifying questions for sections that need improvement
4. Preserving your custom content while ensuring consistency
5. Updating metadata and timestamps appropriately

## Interactive Update Process

### Step 1: Understand Update Requirements

First, let me understand what you'd like to update:

**What needs to be updated in this standard?**
- Specific sections that feel outdated?
- Missing examples or use cases you've encountered?
- New critical rules based on team experience?
- Framework updates or tooling changes?
- AI hint configuration improvements?
- Just a general refresh to match the latest template?

Please describe what prompted this update so I can focus on the right areas.

### Step 2: Load and Analyze Current Standard

After understanding your needs, I'll examine the existing standard:

```bash
# Determine standards directory
if [ -f ".aromcp/.standards-dir" ]; then
    STANDARDS_DIR=$(cat .aromcp/.standards-dir)
else
    STANDARDS_DIR="standards"
fi

# Load the standard using AroMCP read_files
aromcp.read_files(["${STANDARDS_DIR}/{standard-id}.md"])

# Check template for comparison using AroMCP read_files
aromcp.read_files(["~/.claude/templates/code-standards-template.md"])
```

I'll analyze:
- **Missing sections** from the template
- **Outdated patterns** that need modernization
- **Incomplete examples** or explanations
- **Metadata** that needs updating
- **AI hint configuration** completeness

### Step 2: Identify Update Needs

Based on my analysis, I'll present what needs attention:

**📊 Standard Analysis Report:**
```
Standard: {name} ({id})
Last Updated: {date}
Template Version: {current vs standard version}

✅ Complete Sections:
- {list of complete sections}

⚠️  Needs Improvement:
- {section}: {what's missing/outdated}
- {section}: {what's missing/outdated}

❌ Missing Sections:
- {list of missing required sections}

🔄 Metadata Updates Needed:
- {list of metadata fields to update}
```

### Step 3: Update Strategy Selection

How would you like to proceed?

1. **Comprehensive Update** - Review and update all sections
2. **Targeted Update** - Focus on specific sections needing work
3. **Quick Fix** - Just add missing required sections
4. **Metadata Only** - Update frontmatter and timestamps
5. **AI Hints Refresh** - Update for better hint generation

### Step 4: Section-by-Section Updates

For each section needing updates, I'll guide you through:

#### **Critical Rules Update**
Current rules:
{show current rules}

Questions:
- Are these rules still the most critical?
- Any new critical rules based on team experience?
- Should any be downgraded to "Core Requirements"?
- Better way to phrase for clarity?

#### **Examples Update**
Current examples:
{analyze current examples}

What's needed:
- Are examples still using current best practices?
- Do they work with latest framework versions?
- Need examples for new use cases?
- All 4 complexity levels present (minimal/standard/detailed/full)?
- Should Structure & Organization patterns become rules?

For new/updated examples, provide:
1. The complete, working code
2. What specific aspect it demonstrates
3. Common variations to consider

Note: We only need correct implementation examples. Incorrect examples are not used by hints_for_file.

#### **Common Mistakes Update**
Current mistakes section:
{show current}

Questions:
- What NEW mistakes have you seen developers make?
- Any previous "mistakes" that are now acceptable?
- Better ways to explain why these are problematic?

#### **Structure & Organization Update**
- Any new organizational patterns discovered?
- Should existing structure patterns become Critical Rules?
- Updated file naming conventions?
- New directory structures adopted?

Remember: Structure patterns should be converted to actionable rules like:
- "PLACE API routes in app/api/[resource]/route.ts"
- "ORGANIZE services by domain in lib/services/"

#### **AI Hint Metadata Update**
Let's enhance the AI hint configuration:

**Context Triggers:**
- Current triggers: {list current}
- Additional patterns to detect?
- New file types or locations?
- Framework-specific contexts?

**Compression Hints:**
- Can examples be more concise?
- Shareable patterns with other rules?
- Progressive detail levels needed?

### Step 5: Template Compliance Check

I'll ensure your updated standard includes all required template sections:

**Required Sections Checklist:**
- [ ] YAML Frontmatter (complete)
- [ ] Version banner with update description
- [ ] 🚨 Critical Rules (3-5 rules)
- [ ] Overview (problem, solution, benefits)
- [ ] Examples (at least 1 correct implementation)
- [ ] Quick Reference

**Recommended Sections:**
- [ ] Common Mistakes
- [ ] Automation (ESLint/tooling)

### Step 6: Metadata and Versioning

Update the frontmatter:

```yaml
---
id: {unchanged}
name: {update if needed}
category: {update if changed}
tags: {add new relevant tags}
applies_to: {update patterns}
severity: {confirm still appropriate}
updated: {new ISO timestamp}
priority: {update if needed}
dependencies: {add/remove as needed}
description: {update if clearer}
# New fields for AI hints:
context_triggers:
  task_types: [...]
  code_patterns: [...]
  import_indicators: [...]
optimization:
  priority: critical|high|medium|low
  example_reusability: high|medium|low
---
```

Version banner update:
```markdown
_Updated: {date} - {description of changes made}_
```

### Step 7: Validation and Diff Review

Before saving, I'll:

1. **Show you a diff** of all changes
2. **Validate** all required sections are present
3. **Check** examples compile/run correctly
4. **Verify** links and references work
5. **Ensure** formatting is consistent

```bash
# Show diff by reading both files for comparison
aromcp.read_files(["${STANDARDS_DIR}/{id}.md.backup", "${STANDARDS_DIR}/{id}.md"])

# Validate structure by reading and analyzing file
aromcp.read_files(["${STANDARDS_DIR}/{id}.md"])
```

### Step 8: Save and Regenerate

**Save Strategy:**
1. Backup current version: `${STANDARDS_DIR}/{id}.md.backup`
2. Save updated version: `${STANDARDS_DIR}/{id}.md`
3. Update git history if applicable

**Regeneration Needed?**
If we've updated:
- Context triggers
- Rule structures
- Example formats
- ESLint patterns

Then suggest: `claude standards:generate`

## Update Patterns

### Pattern: Adding Missing Sections

If the standard is missing required sections, I'll:
1. Show the template structure for that section
2. Ask for the specific content needed
3. Generate the section following template patterns
4. Integrate it in the correct location

### Pattern: Modernizing Examples

For outdated examples, I'll:
1. Identify what makes them outdated
2. Request updated versions
3. Ensure they follow current framework patterns
4. Add progressive complexity levels if beneficial

### Pattern: Enhancing for AI Hints

To improve AI hint generation:
1. Add detailed context triggers
2. Create multiple example formats (minimal/standard/detailed/full)
3. Add metadata for smart loading
4. Include relationship mappings

## State Management

Updates are tracked for recovery:
```json
{
  "standard_id": "{id}",
  "update_started": "{timestamp}",
  "sections_completed": ["overview", "examples"],
  "sections_remaining": ["automation", "testing"],
  "backup_location": "{standards_dir}/{id}.md.backup"
}
```

## Completion Summary

```
✅ Updated: {standards_dir}/{id}.md
📝 Sections updated: {count}
➕ Sections added: {count}
🔄 Metadata refreshed: Yes/No
📅 Last update: {old date} → {new date}

Changes summary:
- {bullet list of major changes}

Next steps:
1. Review the updated standard
2. Run: claude standards:generate
3. Test the updates in your codebase
4. Share with team for feedback
```