// Global utilities
document.addEventListener('DOMContentLoaded', () => {
    // Set active nav link based on current path
    const links = document.querySelectorAll('.nav-links a');
    const path = window.location.pathname;
    links.forEach(link => {
        link.classList.remove('active');
        const href = link.getAttribute('href');
        if (href === path || (href !== '/' && path.startsWith(href))) {
            link.classList.add('active');
        }
    });
});

// Handle chart resizes on window resize
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        // Each page handles its own chart resizing
    }, 200);
});
