function formatDate(dateString) {
    const [year, month, day] = dateString.split('-');
    return `${month}/${day}/${year}`;
}

async function openPostOverlay(post_id, mountain_photo) {
    const overlay = document.querySelector("#summit-overlay");

    try {
        // Fetch post data
        const response = await fetch(`/post-search?post_id=${encodeURIComponent(post_id)}`);
        if (!response.ok) {
            console.error("Failed to fetch post data");
            return;
        }
        const post = await response.json();

        if (post.code !== 200) {
            console.error("Post not found or error in response");
            return;
        }

        const postData = post.data;

        // Populate left section
        const posterPfp = overlay.querySelector(".post-overlay-pfp");
        const posterUsername = overlay.querySelector(".post-overlay-username");
        const postImage = overlay.querySelector(".post-overlay-post-image");
        const postDate = overlay.querySelector(".post-overlay-date");
        const likeImage = overlay.querySelector(".post-overlay-like-icon");
        const likeCount = overlay.querySelector(".post-overlay-like-count");
        const captionSection = overlay.querySelector(".post-overlay-caption-section p");

        posterPfp.src = `/static/images/user_photos/profile_photos/${postData.poster.profile_photo}`;
        posterPfp.alt = `${postData.poster.username}'s Profile Photo`;
        posterUsername.textContent = postData.poster.username;
        posterUsername.href = `user/${postData.poster.user_id}`;
        if (!postData.picture) {
            postImage.src = `/static/images/mountain_images/${mountain_photo}`;
        } else {
            postImage.src = postData.picture;
        }
        postDate.innerHTML = formatDate(postData.date);
        postImage.alt = `Image of summit by ${postData.poster.username}`;
        if (postData.user_liked == 1){
            likeImage.src = "/static/images/site_resources/liked_heart.png";
        } else {
            likeImage.src = "/static/images/site_resources/unliked_heart.png";
        }
        likeImage.dataset.postId = `${post_id}`;
        likeCount.textContent = `${postData.likes} Likes`;
        captionSection.textContent = postData.caption;

        // Populate right section with comments
        const commentsSection = overlay.querySelector(".post-overlay-comments-section");
        commentsSection.innerHTML = ""; // Clear previous comments
        const commentButton = overlay.querySelector(".post-overlay-comment-post-button");
        commentButton.dataset.postId = post_id;

        if (Array.isArray(postData.comments) && postData.comments.length === 0) {

            const noCommentsDiv = document.createElement("div");
            noCommentsDiv.classList.add("post-overlay-no-comments");
            noCommentsDiv.innerHTML = "Be the first to comment!";
            commentsSection.appendChild(noCommentsDiv);

        } else {


            postData.comments.forEach((comment) => {
                const commentDiv = document.createElement("div");
                commentDiv.classList.add("post-overlay-comment");

                commentDiv.innerHTML = `
                    <img src="/static/images/user_photos/profile_photos/${comment.profile_photo}" 
                        alt="${comment.username}'s Profile Photo" 
                        class="post-overlay-comment-pfp">
                    <div class="post-overlay-comment-content">
                        <a href="user/${comment.user_id}" class="post-overlay-comment-username">${comment.username}</a>
                        <p>${comment.message}</p>
                    </div>
                `;
                commentsSection.appendChild(commentDiv);
            });

        }   
        // Show the overlay
        overlay.classList.remove("hidden");

    } catch (error) {
        console.error("Error loading post overlay:", error);
    }
}

// Close overlay logic
document.querySelector(".post-overlay-close").addEventListener("click", () => {
    const overlay = document.querySelector("#summit-overlay");
    overlay.classList.add("hidden");
});

document.addEventListener("DOMContentLoaded", () => {
    const likeIcon = document.querySelector(".post-overlay-like-icon");
    const likeCount = document.querySelector(".post-overlay-like-count");

    likeIcon.addEventListener("click", async () => {
        const postId = likeIcon.dataset.postId; // Assuming the post ID is stored as a data attribute

        try {
            // Send POST request to toggle like
            const response = await fetch("/toggle-like", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ "post_id": postId })
            });

            const result = await response.json();
            if (result.code === 200) {
                // Update the like count
                likeCount.textContent = `${result.like_count} Likes`;

                // Toggle the like icon
                if (result.liked) {
                    likeIcon.src = "/static/images/site_resources/liked_heart.png";
                } else {
                    likeIcon.src = "/static/images/site_resources/unliked_heart.png";
                }
            } else {
                console.error("Error toggling like:", result.message);
            }
        } catch (error) {
            console.error("Error:", error);
        }
    });
});


document.addEventListener("DOMContentLoaded", () => {
    const commentInput = document.querySelector(".post-overlay-comment-input");
    const commentButton = document.querySelector(".post-overlay-comment-post-button");
    const commentsSection = document.querySelector(".post-overlay-comments-section");

    commentButton.addEventListener("click", async () => {
        const postId = commentButton.dataset.postId; // Assuming the post ID is stored as a data attribute
        const message = commentInput.value.trim();

        if (!message) {
            alert("Comment cannot be empty.");
            return;
        }

        try {
            // Send POST request to add comment
            const response = await fetch("/post-comment", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ post_id: postId, message }),
            });

            const result = await response.json();
            if (result.code === 200) {

                // Remove no comments text when a comment is added
                if(!commentsSection.querySelector(".post-overlay-comment")) {
                    const noCommentMessage = commentsSection.querySelector(".post-overlay-no-comments");
                    noCommentMessage.remove();
                }   

                // Clear the input field
                commentInput.value = "";

                // Add the new comment to the comments section
                const newComment = document.createElement("div");
                newComment.className = "post-overlay-comment";
                newComment.innerHTML = `
                    <img src="/static/images/user_photos/profile_photos/${result.data.profile_photo}" 
                        alt="${result.data.username}'s Profile Photo" class="post-overlay-comment-pfp">
                    <div class="post-overlay-comment-content">
                        <span class="post-overlay-comment-username">${result.data.username}</span>
                        <p>${result.data.comment}</p>
                    </div>
                `;
                commentsSection.appendChild(newComment);
            } else {
                console.error("Error posting comment:", result.message);
            }
        } catch (error) {
            console.error("Error:", error);
        }
    });
});
