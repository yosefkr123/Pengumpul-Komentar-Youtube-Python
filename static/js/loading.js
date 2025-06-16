document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('commentForm');
    const loadingOverlay = document.getElementById('loadingOverlay');
    
    if (form) {
        form.addEventListener('submit', function() {
            loadingOverlay.style.display = 'flex';
        });
    }
});