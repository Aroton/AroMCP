/*
 * @aromcp-rule-id: general-typescript
 * @aromcp-patterns: ["**/*.ts", "**/*.tsx"]
 * @aromcp-severity: info
 * @aromcp-tags: ["typescript", "general"]
 * @aromcp-description: General TypeScript best practices
 */

module.exports = {
    meta: {
        type: 'suggestion',
        docs: {
            description: 'General TypeScript best practices',
            category: 'Best Practices',
            recommended: false
        },
        fixable: null,
        schema: []
    },

    create(context) {
        return {
            // ESLint rule implementation would go here
        };
    }
};