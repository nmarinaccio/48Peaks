# 48Peaks - Design Documentation

## Overview

This document outlines the design of 48Peaks, focusing on the system architecture, database design, key modules, and overall flow of the application. The app allows users to interact with information related to mountains, hikes, and summits, as well as connect with other hikers through comments, likes, and follows.

## System Architecture

48Peaks follows a **client-server** architecture consisting of the following key components:

- **Frontend**: The web-based user interface developed using Flask and HTML templates. It includes pages for user registration, profile management, mountain details, summit posts, and more.
  
- **Backend**: A Flask-based server that handles HTTP requests, routes them to appropriate views, and interacts with the SQLite database for CRUD operations.
  
- **Database**: The app uses **SQLite** to store persistent data, including user profiles, mountain information, summit details, comments, and more.

### Key Features

- **User Authentication & Profiles**: Users can create accounts, log in, and manage their profile with details like bio, profile photo, email, and banner photo.
  
- **Mountain Information**: Users can explore mountains, view their details (name, elevation, location, weather conditions), and see associated summit posts and comments through combined database and API functionality.
  
- **Summit Posts & Comments**: Users can share their hiking experiences, including summit photos and additional notes, and interact with other users via comments on summits and mountains.
  
- **Social Features**: The app supports following other users, liking summit posts, and commenting on various mountain-related content.

---

## Database Design

48Peaks uses SQLite for data persistence, with the following tables:

 ### `users`
 Stores user details and authentication data.

 ### `mountains`
 Contains information about mountains, including their name, elevation, location (in latitude and longitude), and associated photos.   |

 ### `summits`
 Records information about hikes, including the user who hiked, the mountain climbed, and any notes or photos associated with the summit.

 ### `comments`
 Allows users to leave comments on mountains and summits. Includes post and edit timestamps

 ### `summit_comments`
 Similar to the `comments` table, but for comments associated with summit posts.

 ### `followers`
 Tracks user relationships for following and being followed.

 ### `post_likes`
 Tracks which users have liked which summit posts.

## Key Routes

The key routes of 48Peaks are as follows:

- **User Authentication**:
  - `GET, POST /register`: Register a new user
  - `GET, POST /login`: Log in an existing user
  - `GET /logout`: Log out the current user

- **Profile**:
  - `GET /profile/<int:user_id>`: Display profile page
  - `GET, POST /profile/edit`: Update bio, email, photos, etc...
  - `POST /change_password`: Password change and secure password hash

- **Mountain Information**:
  - `GET /mountains`: List all mountains
  - `GET /mountain/<int:mountain_id>`: View details of a specific mountain
  
- **Summits**:
  - `POST /summit`: Create a new summit post
  - `GET, POST /summit/<int:summit_id>/edit`: Edit details about a specific summit post
  - `POST /summit/<int:summit_id>/comment`: Post a comment on a summit
  - `POST /summit/<int:summit_id>/delete`: Delete a specific summit record
  
- **Social Features**:
  - `POST /follow/<int:folowee_id>`: Follow another user
  - `POST /unfollow/<int:folowee_id>`: Unfollow another user
  - `POST /likes/<int:post_id>`: Like or unlike a summit post
  - `POST /comment/<int:mountain_id>`: Comment on a specific mountain page
  - `POST /comment/<int:comment_id>/edit`: Edit an existing comment
  - `POST /comment/<int:comment_id>/delete`: Delete a specific comment

- **Static/Utility**:
  - `GET /`: Displays the homepage, welcomes user, provides navigation options
  - `GET /admin`: Restricted access to manage users, mountains, etc...
  - `GET /search`: Allows users to search for mountains, users, summits


## Dependencies

The project requires the following libraries:

- **Flask**: For routing and handling HTTP requests.
- **Flask-Session**: For handling user sessions.
- **pillow**: For image processing (e.g., handling user profile pictures).
- **pytz**: For timezone management.
- **requests**: For making HTTP requests to external APIs.
- **Werkzeug**: For handling secure password hashing and other utility functions.
---

## Conclusion

48Peaks is designed with a clean, modular approach, allowing users to interact with each other and explore mountains through summit posts, comments, and social connections. The system is built to be scalable, with easy-to-understand routes, database relationships, and user interface components.
