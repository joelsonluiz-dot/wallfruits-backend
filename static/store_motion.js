(function initStoreMotion(window, document) {
    "use strict";

    if (!window || !document || window.WFStoreMotion) {
        return;
    }

    var reducedMotion = false;
    try {
        reducedMotion = Boolean(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    } catch (error) {
        reducedMotion = false;
    }

    var revealObserver = null;
    var revealObserverConfigKey = "";
    var revealSet = new WeakSet();
    var rippleBound = false;
    var autoRefreshObserver = null;
    var autoRefreshTimer = 0;

    var activeProfileName = "standard";
    var activeProfileOverrides = {};
    var activeProfile = null;

    var defaultRevealSelectors = [
        ".loja-section",
        ".loja-card",
        ".cartp-item",
        ".ordersp-card",
        ".propp-card",
        ".checkp-item",
        ".detail-card",
        ".detail-related-card",
        ".ag-metric",
        ".ag-form-card",
        ".ag-table-wrap",
        ".ag-auth-alert",
        ".store-motion-card",
        ".wf-card",
        ".wf-alert",
        ".wf-topbar",
        ".wf-sidebar-right-section",
        ".wf-restricted-card",
        ".wf-hidden-settings",
        ".card"
    ];

    var profileConfigs = {
        standard: {
            revealSelectors: defaultRevealSelectors,
            delayStep: 24,
            maxDelay: 280,
            threshold: 0.12,
            rootMargin: "0px 0px -8% 0px",
            autoRefreshThrottle: 180,
            enableRipple: true,
            revealDistancePx: 14,
            revealScale: 0.985,
            opacityDurationMs: 460,
            transformDurationMs: 580,
            pressScale: 0.985,
            rippleColor: "rgba(255,255,255,0.34)"
        },
        showcase: {
            revealSelectors: defaultRevealSelectors,
            delayStep: 28,
            maxDelay: 320,
            threshold: 0.1,
            rootMargin: "0px 0px -10% 0px",
            autoRefreshThrottle: 190,
            enableRipple: true,
            revealDistancePx: 16,
            revealScale: 0.982,
            opacityDurationMs: 520,
            transformDurationMs: 620,
            pressScale: 0.983,
            rippleColor: "rgba(255,255,255,0.32)"
        },
        dense: {
            revealSelectors: [
                ".wf-card",
                ".card",
                ".store-motion-card",
                ".wf-alert",
                ".table-responsive",
                ".wf-topbar"
            ],
            delayStep: 16,
            maxDelay: 180,
            threshold: 0.18,
            rootMargin: "0px 0px -5% 0px",
            autoRefreshThrottle: 140,
            enableRipple: true,
            revealDistancePx: 9,
            revealScale: 0.992,
            opacityDurationMs: 280,
            transformDurationMs: 340,
            pressScale: 0.988,
            rippleColor: "rgba(255,255,255,0.26)"
        },
        chat: {
            revealSelectors: [
                ".wf-card",
                ".chat-main-card",
                ".panel-card",
                ".wf-alert",
                ".store-motion-card"
            ],
            delayStep: 10,
            maxDelay: 120,
            threshold: 0.2,
            rootMargin: "0px 0px -4% 0px",
            autoRefreshThrottle: 110,
            enableRipple: true,
            revealDistancePx: 7,
            revealScale: 0.994,
            opacityDurationMs: 220,
            transformDurationMs: 280,
            pressScale: 0.99,
            rippleColor: "rgba(255,255,255,0.22)"
        },
        minimal: {
            revealSelectors: [
                ".wf-card",
                ".card",
                ".wf-alert",
                ".store-motion-card"
            ],
            delayStep: 0,
            maxDelay: 0,
            threshold: 0.28,
            rootMargin: "0px 0px -2% 0px",
            autoRefreshThrottle: 220,
            enableRipple: false,
            revealDistancePx: 4,
            revealScale: 0.998,
            opacityDurationMs: 160,
            transformDurationMs: 200,
            pressScale: 0.992,
            rippleColor: "rgba(255,255,255,0.14)"
        }
    };

    function numberOrFallback(value, fallback) {
        var num = Number(value);
        return Number.isFinite(num) ? num : fallback;
    }

    function clamp(value, min, max) {
        if (!Number.isFinite(value)) {
            return min;
        }

        return Math.min(max, Math.max(min, value));
    }

    function roundTo(value, digits) {
        var factor = Math.pow(10, digits || 0);
        return Math.round(value * factor) / factor;
    }

    function toSelectorArray(selectors) {
        if (!selectors) {
            return defaultRevealSelectors.slice();
        }

        if (Array.isArray(selectors)) {
            return selectors.filter(function onlyStrings(item) {
                return typeof item === "string" && item.trim().length > 0;
            });
        }

        if (typeof selectors === "string" && selectors.trim().length > 0) {
            return selectors
                .split(",")
                .map(function trimEach(part) { return part.trim(); })
                .filter(Boolean);
        }

        return defaultRevealSelectors.slice();
    }

    function normalizeProfileName(name) {
        var normalized = String(name || "").trim().toLowerCase();
        return Object.prototype.hasOwnProperty.call(profileConfigs, normalized)
            ? normalized
            : "standard";
    }

    function detectProfileFromPath(pathname) {
        var path = String(pathname || (window.location && window.location.pathname) || "").toLowerCase();

        if (path.indexOf("/messages") === 0) {
            return "chat";
        }

        if (
            path.indexOf("/admin") === 0
            || path.indexOf("/clients/manage") === 0
            || path.indexOf("/services/manage") === 0
            || path.indexOf("/store/manage") === 0
        ) {
            return "dense";
        }

        if (path.indexOf("/library") === 0 || path.indexOf("/reader") === 0) {
            return "showcase";
        }

        if (path.indexOf("/store") === 0) {
            return "showcase";
        }

        if (/^\/(login|register|forgot-password|reset-password|forgot_password|forgot-password-confirmation|forgot_password_confirmation)/.test(path)) {
            return "minimal";
        }

        return "standard";
    }

    function getDeviceHints() {
        var width = Number(window.innerWidth || 0);
        var isMobileViewport = width > 0 && width < 768;
        var isTabletViewport = width >= 768 && width < 1024;
        var isSmallViewport = width > 0 && width < 1024;
        var isCoarsePointer = false;
        var saveData = false;
        var effectiveType = "";
        var downlink = numberOrFallback(window.navigator && window.navigator.connection && window.navigator.connection.downlink, NaN);
        var deviceMemory = numberOrFallback(window.navigator && window.navigator.deviceMemory, NaN);
        var hardwareConcurrency = numberOrFallback(window.navigator && window.navigator.hardwareConcurrency, NaN);

        try {
            isCoarsePointer = Boolean(window.matchMedia && window.matchMedia("(pointer: coarse)").matches);
        } catch (error) {
            isCoarsePointer = false;
        }

        try {
            saveData = Boolean(window.navigator && window.navigator.connection && window.navigator.connection.saveData);
        } catch (error) {
            saveData = false;
        }

        try {
            effectiveType = String(window.navigator && window.navigator.connection && window.navigator.connection.effectiveType || "").toLowerCase();
        } catch (error) {
            effectiveType = "";
        }

        var lowMemory = Number.isFinite(deviceMemory) && deviceMemory > 0 && deviceMemory <= 4;
        var lowCpu = Number.isFinite(hardwareConcurrency) && hardwareConcurrency > 0 && hardwareConcurrency <= 4;
        var veryLowMemory = Number.isFinite(deviceMemory) && deviceMemory > 0 && deviceMemory <= 2;
        var veryLowCpu = Number.isFinite(hardwareConcurrency) && hardwareConcurrency > 0 && hardwareConcurrency <= 2;

        var tier = "high";
        if (reducedMotion || saveData || effectiveType.indexOf("2g") >= 0 || veryLowMemory || veryLowCpu) {
            tier = "ultra-low";
        } else if (effectiveType.indexOf("3g") >= 0 || lowMemory || lowCpu) {
            tier = "low";
        } else if (isSmallViewport || isCoarsePointer || isTabletViewport || isMobileViewport) {
            tier = "medium";
        }

        return {
            tier: tier,
            width: width,
            isMobileViewport: isMobileViewport,
            isTabletViewport: isTabletViewport,
            isCoarsePointer: isCoarsePointer,
            saveData: saveData,
            effectiveType: effectiveType,
            downlink: downlink,
            deviceMemory: deviceMemory,
            hardwareConcurrency: hardwareConcurrency,
            reducedMotion: reducedMotion
        };
    }

    function sanitizeProfile(profile) {
        var merged = Object.assign({}, profile || {});
        merged.revealSelectors = toSelectorArray(merged.revealSelectors);
        merged.delayStep = Math.max(0, numberOrFallback(merged.delayStep, 24));
        merged.maxDelay = Math.max(0, numberOrFallback(merged.maxDelay, 280));
        merged.threshold = clamp(numberOrFallback(merged.threshold, 0.12), 0, 1);
        merged.autoRefreshThrottle = Math.max(80, numberOrFallback(merged.autoRefreshThrottle, 180));
        merged.rootMargin = typeof merged.rootMargin === "string" && merged.rootMargin.trim().length
            ? merged.rootMargin.trim()
            : "0px 0px -8% 0px";
        merged.revealDistancePx = Math.max(0, numberOrFallback(merged.revealDistancePx, 14));
        merged.revealScale = clamp(numberOrFallback(merged.revealScale, 0.985), 0.9, 1);
        merged.opacityDurationMs = Math.max(120, numberOrFallback(merged.opacityDurationMs, 460));
        merged.transformDurationMs = Math.max(140, numberOrFallback(merged.transformDurationMs, 580));
        merged.pressScale = clamp(numberOrFallback(merged.pressScale, 0.985), 0.95, 1);
        merged.enableRipple = merged.enableRipple !== false;
        merged.rippleColor = typeof merged.rippleColor === "string" && merged.rippleColor.trim().length
            ? merged.rippleColor.trim()
            : "rgba(255,255,255,0.34)";
        return merged;
    }

    function adaptProfileForDevice(profile, hints) {
        var adapted = sanitizeProfile(profile);
        var tier = hints && hints.tier ? hints.tier : "high";

        if (tier === "ultra-low") {
            adapted.delayStep = 0;
            adapted.maxDelay = 0;
            adapted.threshold = clamp(adapted.threshold + 0.14, 0, 1);
            adapted.autoRefreshThrottle = Math.max(adapted.autoRefreshThrottle, 280);
            adapted.enableRipple = false;
            adapted.revealDistancePx = 0;
            adapted.revealScale = 1;
            adapted.opacityDurationMs = 120;
            adapted.transformDurationMs = 130;
            adapted.pressScale = 1;
            adapted.rippleColor = "rgba(255,255,255,0.14)";
        } else if (tier === "low") {
            adapted.delayStep = 0;
            adapted.maxDelay = Math.min(adapted.maxDelay, 120);
            adapted.threshold = clamp(adapted.threshold + 0.1, 0, 1);
            adapted.autoRefreshThrottle = Math.max(adapted.autoRefreshThrottle, 240);
            adapted.enableRipple = false;
            adapted.revealDistancePx = Math.min(adapted.revealDistancePx, 6);
            adapted.revealScale = Math.max(adapted.revealScale, 0.996);
            adapted.opacityDurationMs = Math.min(adapted.opacityDurationMs, 220);
            adapted.transformDurationMs = Math.min(adapted.transformDurationMs, 260);
            adapted.pressScale = Math.max(adapted.pressScale, 0.992);
            adapted.rippleColor = "rgba(255,255,255,0.18)";
        } else if (tier === "medium") {
            adapted.delayStep = Math.round(adapted.delayStep * 0.65);
            adapted.maxDelay = Math.round(adapted.maxDelay * 0.7);
            adapted.threshold = clamp(adapted.threshold + 0.04, 0, 1);
            adapted.autoRefreshThrottle = Math.max(adapted.autoRefreshThrottle, 180);
            adapted.revealDistancePx = Math.round(adapted.revealDistancePx * 0.7);
            adapted.revealScale = roundTo(Math.max(adapted.revealScale, 0.99), 3);
            adapted.opacityDurationMs = Math.round(adapted.opacityDurationMs * 0.75);
            adapted.transformDurationMs = Math.round(adapted.transformDurationMs * 0.76);
            adapted.pressScale = roundTo(Math.max(adapted.pressScale, 0.989), 3);
            adapted.rippleColor = "rgba(255,255,255,0.24)";
        }

        if (hints && hints.reducedMotion) {
            adapted.delayStep = 0;
            adapted.maxDelay = 0;
            adapted.enableRipple = false;
            adapted.revealDistancePx = 0;
            adapted.revealScale = 1;
            adapted.opacityDurationMs = 120;
            adapted.transformDurationMs = 120;
        }

        return sanitizeProfile(adapted);
    }

    function resolveProfile(name, overrides) {
        var profileName = normalizeProfileName(name);
        var merged = Object.assign({}, profileConfigs.standard, profileConfigs[profileName] || {});

        if (overrides && typeof overrides === "object") {
            merged = Object.assign(merged, overrides);
        }

        merged = sanitizeProfile(merged);
        var hints = getDeviceHints();
        merged = adaptProfileForDevice(merged, hints);
        merged.deviceTier = hints.tier;
        merged.deviceHints = hints;
        return merged;
    }

    function applyMotionVars(profile) {
        if (!profile || !(document.documentElement instanceof HTMLElement)) {
            return;
        }

        var root = document.documentElement;
        root.style.setProperty("--wf-reveal-distance", String(profile.revealDistancePx) + "px");
        root.style.setProperty("--wf-reveal-scale", String(profile.revealScale));
        root.style.setProperty("--wf-reveal-opacity-duration", String(profile.opacityDurationMs) + "ms");
        root.style.setProperty("--wf-reveal-transform-duration", String(profile.transformDurationMs) + "ms");
        root.style.setProperty("--wf-press-scale", String(profile.pressScale));
        root.style.setProperty("--wf-ripple-color", String(profile.rippleColor));
    }

    function ensureStyles() {
        if (document.getElementById("wf-store-motion-style")) {
            return;
        }

        var style = document.createElement("style");
        style.id = "wf-store-motion-style";
        style.textContent = ""
            + ":root{--wf-reveal-distance:14px;--wf-reveal-scale:0.985;--wf-reveal-opacity-duration:460ms;--wf-reveal-transform-duration:580ms;--wf-press-scale:0.985;--wf-ripple-color:rgba(255,255,255,0.34);}"
            + ".wf-reveal{opacity:0;transform:translate3d(0,var(--wf-reveal-distance),0) scale(var(--wf-reveal-scale));will-change:opacity,transform;}"
            + ".wf-reveal.is-visible{opacity:1;transform:none;transition:opacity var(--wf-reveal-opacity-duration) cubic-bezier(.2,.7,.2,1),transform var(--wf-reveal-transform-duration) cubic-bezier(.2,.7,.2,1);transition-delay:var(--wf-reveal-delay,0ms);will-change:auto;}"
            + ".wf-pressable{position:relative;overflow:hidden;transform:translateZ(0);transition:transform .14s ease,box-shadow .22s ease;}"
            + ".wf-pressable:active{transform:scale(var(--wf-press-scale));}"
            + ".wf-ripple-wave{position:absolute;border-radius:999px;pointer-events:none;background:var(--wf-ripple-color);transform:scale(0);animation:wfStoreRipple .54s cubic-bezier(.2,.7,.2,1) forwards;}"
            + "@keyframes wfStoreRipple{to{transform:scale(2.7);opacity:0;}}"
            + "@media (prefers-reduced-motion: reduce){.wf-reveal,.wf-reveal.is-visible,.wf-pressable{transition:none !important;animation:none !important;transform:none !important;opacity:1 !important;}}";
        document.head.appendChild(style);
    }

    function batchMutate(fn) {
        if (typeof fn !== "function") {
            return;
        }

        window.requestAnimationFrame(function runMutation() {
            fn();
        });
    }

    function defer(task) {
        if (typeof task !== "function") {
            return;
        }

        if ("requestIdleCallback" in window) {
            window.requestIdleCallback(function onIdle() {
                task();
            }, { timeout: 350 });
            return;
        }

        window.setTimeout(task, 64);
    }

    function markPressables(root) {
        var scope = root && root.querySelectorAll ? root : document;
        var nodes = scope.querySelectorAll(
            "[data-wf-press], .ripple, .btn, .wf-nav-link, .wf-nav-btn, .wf-mobile-nav-item, .wf-popup-item, .wf-sidebar-right-item, .wf-profile-link, .wf-profile-trigger, .wf-menu-toggle, .wf-community-toggle, .wf-messages-toggle, .wf-ai-fab, .wf-cart-fab, .wf-mobile-floating-add"
        );

        nodes.forEach(function addClass(node) {
            node.classList.add("wf-pressable");
        });
    }

    function optimizeImages(root) {
        var scope = root && root.querySelectorAll ? root : document;
        var images = scope.querySelectorAll("img");

        images.forEach(function optimize(image, index) {
            if (!image.getAttribute("loading")) {
                image.setAttribute("loading", "lazy");
            }

            if (!image.getAttribute("decoding")) {
                image.setAttribute("decoding", "async");
            }

            if (image.dataset && image.dataset.wfPriority === "high") {
                image.setAttribute("fetchpriority", "high");
            } else if (!image.getAttribute("fetchpriority") && index < 2) {
                image.setAttribute("fetchpriority", "auto");
            }
        });
    }

    function revealElement(node) {
        if (!(node instanceof HTMLElement)) {
            return;
        }

        node.classList.add("is-visible");
        if (revealObserver) {
            revealObserver.unobserve(node);
        }
    }

    function observeRevealTargets(root, selectors, motionConfig) {
        var scope = root && root.querySelectorAll ? root : document;
        var list = toSelectorArray(selectors);
        if (!list.length) {
            return;
        }

        var targets = scope.querySelectorAll(list.join(","));
        if (!targets.length) {
            return;
        }

        var threshold = clamp(numberOrFallback(motionConfig && motionConfig.threshold, 0.12), 0, 1);
        var rootMargin = motionConfig && typeof motionConfig.rootMargin === "string" && motionConfig.rootMargin.trim().length > 0
            ? motionConfig.rootMargin.trim()
            : "0px 0px -8% 0px";

        var delayStep = Math.max(0, numberOrFallback(motionConfig && motionConfig.delayStep, 24));
        var maxDelay = Math.max(0, numberOrFallback(motionConfig && motionConfig.maxDelay, 280));

        var observerConfigKey = String(threshold) + "|" + rootMargin;
        if (revealObserver && revealObserverConfigKey !== observerConfigKey) {
            revealObserver.disconnect();
            revealObserver = null;
        }

        targets.forEach(function setupNode(node, index) {
            if (!(node instanceof HTMLElement)) {
                return;
            }

            if (revealSet.has(node) || node.classList.contains("wf-reveal-static")) {
                return;
            }

            revealSet.add(node);
            node.classList.add("wf-reveal");
            node.style.setProperty("--wf-reveal-delay", String(Math.min(index * delayStep, maxDelay)) + "ms");

            if (reducedMotion || !("IntersectionObserver" in window)) {
                node.classList.add("is-visible");
                return;
            }

            if (!revealObserver) {
                revealObserver = new IntersectionObserver(function onIntersect(entries) {
                    entries.forEach(function checkEntry(entry) {
                        if (entry.isIntersecting) {
                            revealElement(entry.target);
                        }
                    });
                }, {
                    threshold: threshold,
                    rootMargin: rootMargin
                });
                revealObserverConfigKey = observerConfigKey;
            }

            revealObserver.observe(node);
        });
    }

    function handleRipple(event) {
        if ((activeProfile && activeProfile.enableRipple === false) || reducedMotion) {
            return;
        }

        var target = event.target instanceof Element ? event.target : null;
        if (!target) {
            return;
        }

        var trigger = target.closest(".wf-pressable, [data-wf-press], .ripple");
        if (!(trigger instanceof HTMLElement)) {
            return;
        }

        var rect = trigger.getBoundingClientRect();
        var size = Math.max(rect.width, rect.height);
        if (!size || !Number.isFinite(size)) {
            return;
        }

        var ripple = document.createElement("span");
        ripple.className = "wf-ripple-wave";
        ripple.style.width = String(size) + "px";
        ripple.style.height = String(size) + "px";

        var clientX = numberOrFallback(event.clientX, 0);
        var clientY = numberOrFallback(event.clientY, 0);
        ripple.style.left = String(clientX - rect.left - (size / 2)) + "px";
        ripple.style.top = String(clientY - rect.top - (size / 2)) + "px";

        trigger.appendChild(ripple);
        window.setTimeout(function cleanupRipple() {
            ripple.remove();
        }, 560);
    }

    function bindGlobalRipple() {
        if (rippleBound) {
            return;
        }

        document.addEventListener("pointerdown", handleRipple, { passive: true });
        rippleBound = true;
    }

    function setProfile(name, overrides) {
        activeProfileName = normalizeProfileName(name || detectProfileFromPath(window.location && window.location.pathname));
        activeProfileOverrides = overrides && typeof overrides === "object" ? Object.assign({}, overrides) : {};
        activeProfile = resolveProfile(activeProfileName, activeProfileOverrides);

        ensureStyles();
        applyMotionVars(activeProfile);

        if (revealObserver) {
            revealObserver.disconnect();
            revealObserver = null;
            revealObserverConfigKey = "";
        }

        return getProfile();
    }

    function retuneForDevice() {
        activeProfile = resolveProfile(activeProfileName, activeProfileOverrides);
        applyMotionVars(activeProfile);
        return getProfile();
    }

    function getProfile() {
        var profile = activeProfile || resolveProfile(activeProfileName, activeProfileOverrides);
        return {
            name: activeProfileName,
            deviceTier: profile.deviceTier,
            config: Object.assign({}, profile, {
                revealSelectors: toSelectorArray(profile.revealSelectors),
                deviceHints: Object.assign({}, profile.deviceHints || getDeviceHints())
            })
        };
    }

    function refresh(root, options) {
        var config = options || {};
        var profile = activeProfile || resolveProfile(activeProfileName, activeProfileOverrides);

        ensureStyles();
        applyMotionVars(profile);
        markPressables(root);

        var effectiveSelectors = config.revealSelectors || profile.revealSelectors || defaultRevealSelectors;
        var motionConfig = {
            delayStep: numberOrFallback(config.delayStep, profile.delayStep),
            maxDelay: numberOrFallback(config.maxDelay, profile.maxDelay),
            threshold: numberOrFallback(config.threshold, profile.threshold),
            rootMargin: typeof config.rootMargin === "string" && config.rootMargin.trim().length
                ? config.rootMargin
                : profile.rootMargin
        };

        batchMutate(function runReveal() {
            observeRevealTargets(root, effectiveSelectors, motionConfig);
        });

        defer(function runImageOptimization() {
            optimizeImages(root);
        });
    }

    function installAutoRefresh(root, options) {
        if (!("MutationObserver" in window)) {
            return null;
        }

        if (autoRefreshObserver) {
            autoRefreshObserver.disconnect();
            autoRefreshObserver = null;
        }

        var config = options || {};
        var profile = activeProfile || resolveProfile(activeProfileName, activeProfileOverrides);
        var scope = root && root.nodeType === 1 ? root : document.body;
        var revealSelectors = config.revealSelectors || profile.revealSelectors || defaultRevealSelectors;
        var throttleMs = Math.max(80, numberOrFallback(config.throttleMs, profile.autoRefreshThrottle));
        var pendingRoot = null;

        function scheduleRefresh(nextRoot) {
            if (nextRoot && nextRoot.nodeType === 1) {
                pendingRoot = nextRoot;
            }

            if (autoRefreshTimer) {
                return;
            }

            autoRefreshTimer = window.setTimeout(function runRefresh() {
                autoRefreshTimer = 0;
                refresh(pendingRoot || scope, { revealSelectors: revealSelectors });
                pendingRoot = null;
            }, throttleMs);
        }

        autoRefreshObserver = new MutationObserver(function onMutation(mutations) {
            var found = false;

            mutations.forEach(function handleMutation(mutation) {
                if (found || mutation.type !== "childList" || !mutation.addedNodes || !mutation.addedNodes.length) {
                    return;
                }

                for (var index = 0; index < mutation.addedNodes.length; index += 1) {
                    var node = mutation.addedNodes[index];
                    if (node && node.nodeType === 1) {
                        scheduleRefresh(node);
                        found = true;
                        break;
                    }
                }
            });
        });

        autoRefreshObserver.observe(scope, {
            childList: true,
            subtree: true
        });

        return autoRefreshObserver;
    }

    function stopAutoRefresh() {
        if (autoRefreshObserver) {
            autoRefreshObserver.disconnect();
            autoRefreshObserver = null;
        }

        if (autoRefreshTimer) {
            window.clearTimeout(autoRefreshTimer);
            autoRefreshTimer = 0;
        }
    }

    window.WFStoreMotion = {
        refresh: refresh,
        setProfile: setProfile,
        getProfile: getProfile,
        retuneForDevice: retuneForDevice,
        detectProfileFromPath: detectProfileFromPath,
        getDeviceHints: getDeviceHints,
        batchMutate: batchMutate,
        defer: defer,
        optimizeImages: optimizeImages,
        installAutoRefresh: installAutoRefresh,
        stopAutoRefresh: stopAutoRefresh,
        revealSelectors: defaultRevealSelectors.slice(),
        profiles: Object.keys(profileConfigs)
    };

    setProfile(detectProfileFromPath(window.location && window.location.pathname));

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function onReady() {
            refresh(document);
            bindGlobalRipple();
        }, { once: true });
    } else {
        refresh(document);
        bindGlobalRipple();
    }
})(window, document);
