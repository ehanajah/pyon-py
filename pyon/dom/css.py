def inject_scoped_css(css_registry: dict[str, str]) -> None:
    """Invoke JS to parse and inject scoped CSS into the document head."""
    from pyon.browser import ffi, js

    js_code = """                                                                                                              
    if (!window.__pyonInjectScopedCss) {
        window.__pyonInjectScopedCss = function(cssMap) {
            if (!document.getElementById("pyon-scoped-css")) {
                const styleTag = document.createElement("style");
                styleTag.id = "pyon-scoped-css";
                document.head.appendChild(styleTag);
            }
            const finalStyleTag = document.getElementById("pyon-scoped-css");

            const doc = document.implementation.createHTMLDocument("");
            const tempStyle = doc.createElement("style");
            doc.body.appendChild(tempStyle);

            let allScopedCss = "";

            function processRules(rules, scopeId) {                                                                            
                let result = "";
                for (let rule of rules) {
                    if (rule instanceof CSSStyleRule) {
                        let selectors = rule.selectorText.split(",");
                        let scopedSelectors = selectors.map(s => {
                            s = s.trim();
                            const pseudoMatch = s.match(/(::?[a-zA-Z0-9_-]+)+$/);
                            if (pseudoMatch) {
                                const base = s.slice(0, pseudoMatch.index);
                                return `${base}[data-${scopeId}]${pseudoMatch[0]}`;
                            }
                            return `${s}[data-${scopeId}]`;
                        });
                        result += `${scopedSelectors.join(", ")} { ${rule.style.cssText} }\\n`;
                    } else if (rule instanceof CSSMediaRule) {
                        let mediaCss = processRules(rule.cssRules, scopeId);
                        result += `@media ${rule.conditionText} { \\n${mediaCss} }\\n`;
                    } else if (rule instanceof CSSKeyframesRule) {
                            result += rule.cssText + "\\n";
                    } else {
                        result += rule.cssText + "\\n";
                    }
                }
                return result;
            }

            const registry = cssMap instanceof Map ? Object.fromEntries(cssMap) : cssMap;
  
            for (const [scopeId, cssText] of Object.entries(registry)) {
                tempStyle.textContent = cssText;
                allScopedCss += `/* Scope: ${scopeId} */\\n`;
                allScopedCss += processRules(tempStyle.sheet.cssRules, scopeId);
            }

            finalStyleTag.textContent = allScopedCss;
        };
    }
    """
    js.window.eval(js_code) # type: ignore
    js_registry = ffi.to_js(css_registry)
    js.window.__pyonInjectScopedCss(js_registry) # type: ignore
    