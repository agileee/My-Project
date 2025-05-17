from app import create_app

app = create_app()  # Create the Flask app instance

if __name__ == '__main__':
    app.run(debug=True)  # Run the app in debug mode (auto-restarts on changes)

