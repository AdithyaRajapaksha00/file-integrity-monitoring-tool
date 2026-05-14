$(document).ready(function() {
    $("#signup-form").on("submit", function(e) {
        e.preventDefault();

        const formData = new FormData(this);
        const email = formData.get("email");
        const password = formData.get("password");
        const confirmPassword = formData.get("confirm_password");
        const profilePic = formData.get("profile_pic");

        if (!email || !password || !confirmPassword || !profilePic) {
            showError("All fields are required.");
            return;
        }

        if (password !== confirmPassword) {
            showError("Passwords do not match.");
            return;
        }

        $.ajax({
            url: "/signup",
            method: "POST",
            data: formData,
            processData: false,
            contentType: false,
            success: function() {
                window.location.href = "/login";
            },
            error: function(xhr) {
                showError(xhr.responseText || "Signup failed.");
            }
        });
    });

    function showError(msg) {
        $("#error-message").text(msg);
    }
});
