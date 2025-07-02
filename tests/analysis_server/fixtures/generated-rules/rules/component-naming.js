/*
 * @aromcp-rule-id: component-naming
 * @aromcp-patterns: ["**/components/**/*.tsx", "**/components/**/*.jsx"]
 * @aromcp-severity: warn
 * @aromcp-tags: ["components", "react", "naming"]
 * @aromcp-description: Enforce consistent component naming conventions
 */

module.exports = {
    meta: {
        type: 'suggestion',
        docs: {
            description: 'Enforce consistent component naming conventions',
            category: 'Stylistic Issues',
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