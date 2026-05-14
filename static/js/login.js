$(document).ready(function() {
    $("#login-form").on("submit", function(e) {
        e.preventDefault();

        const email = $("input[name='email']").val();
        const password = $("input[name='password']").val();

        if (!email || !password) {
            showError("All fields are required.");
            return;
        }

        $.ajax({
            url: "/login",
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify({ email, password }),
            success: function(response) {
                window.location.href = "/dashboard";
            },
            error: function(xhr) {
                showError(xhr.responseText || "Login failed.");
            }
        });
    });

    function showError(msg) {
        $("#login-error").text(msg);
    }
});
