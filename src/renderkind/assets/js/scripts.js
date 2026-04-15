/**
 * Cleaning Guide UI Interactions
 * Handles TOC toggle, slide animations, and accessibility
 */

(function() {
    'use strict';

    // DOM elements
    const tocToggle = document.getElementById('toc-toggle');
    const tocPanel = document.getElementById('toc-panel');
    const tocClose = document.getElementById('toc-close');
    const tocOverlay = document.getElementById('toc-overlay');

    // State
    let isTocOpen = false;

    /**
     * Open the TOC panel
     */
    function openToc() {
        if (!tocPanel) return;
        tocPanel.classList.add('open');
        if (tocOverlay) tocOverlay.classList.add('active');
        if (tocToggle) tocToggle.setAttribute('aria-expanded', 'true');
        isTocOpen = true;
        document.body.style.overflow = 'hidden';
    }

    /**
     * Close the TOC panel
     */
    function closeToc() {
        if (!tocPanel) return;
        tocPanel.classList.remove('open');
        if (tocOverlay) tocOverlay.classList.remove('active');
        if (tocToggle) tocToggle.setAttribute('aria-expanded', 'false');
        isTocOpen = false;
        document.body.style.overflow = '';
    }

    /**
     * Toggle the TOC panel
     */
    function toggleToc() {
        if (isTocOpen) {
            closeToc();
        } else {
            openToc();
        }
    }

    /**
     * Wrap tables in responsive container
     */
    function wrapTables() {
        const tables = document.querySelectorAll('#main-content table');
        tables.forEach(table => {
            // Avoid double-wrapping
            if (table.parentElement && !table.parentElement.classList.contains('table-responsive')) {
                const wrapper = document.createElement('div');
                wrapper.className = 'table-responsive';
                table.parentNode.insertBefore(wrapper, table);
                wrapper.appendChild(table);
            }
        });
    }

    /**
     * Smooth scroll to an anchor link
     */
    function smoothScroll(e) {
        e.preventDefault();
        const targetId = this.getAttribute('href').substring(1);
        const targetElement = document.getElementById(targetId);
        if (targetElement) {
            closeToc();
            targetElement.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
            // Update URL hash without jumping
            history.pushState(null, null, `#${targetId}`);
        }
    }

    /**
     * Initialize event listeners
     */
    function init() {
        // Toggle button
        if (tocToggle) {
            tocToggle.addEventListener('click', toggleToc);
        }

        // Close button
        if (tocClose) {
            tocClose.addEventListener('click', closeToc);
        }

        // Overlay click
        if (tocOverlay) {
            tocOverlay.addEventListener('click', closeToc);
        }

        // Escape key closes TOC
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && isTocOpen) {
                closeToc();
            }
        });

        // Smooth scroll for TOC links (and main site title in header)
        document.querySelectorAll('.toc-list a, .site-title a').forEach(anchor => {
            anchor.addEventListener('click', smoothScroll);
        });

        // Wrap tables after content loads
        wrapTables();
    }

    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();