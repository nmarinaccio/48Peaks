document.addEventListener("DOMContentLoaded", function () {
    const profileDropdown = document.getElementById("profileDropdown");
    const dropdownMenu = document.getElementById("dropdownMenu");

    // Toggle dropdown menu on click
    profileDropdown.addEventListener("click", function (event) {
        // Prevent the click from propagating to the document
        event.stopPropagation();

        // Add or remove the "show" class with animation
        if (dropdownMenu.classList.contains("show")) {
            dropdownMenu.classList.remove("show");
            setTimeout(() => {
                dropdownMenu.style.display = "none";
            }, 500); // Match the duration of the CSS transition
        } else {
            dropdownMenu.style.display = "flex"; // Ensure the menu is visible before animation
            setTimeout(() => {
                dropdownMenu.classList.add("show");
            }, 10); // Slight delay to trigger the animation
        }
    });

    // Close the dropdown menu when clicking outside of it
    document.addEventListener("click", function () {
        if (dropdownMenu.classList.contains("show")) {
            dropdownMenu.classList.remove("show");
            setTimeout(() => {
                dropdownMenu.style.display = "none";
            }, 500); // Match the duration of the CSS transition
        }
    });
});
