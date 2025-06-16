document.addEventListener('DOMContentLoaded', function() {
    $('#commentsTable').DataTable({
        responsive: true,
        pageLength: 25,
        lengthMenu: [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]],
        language: {
            search: "_INPUT_",
            searchPlaceholder: "Search comments...",
            lengthMenu: "Show _MENU_ comments",
            info: "Showing _START_ to _END_ of _TOTAL_ comments",
            infoEmpty: "No comments available",
            zeroRecords: "No matching comments found"
        }
    });
});