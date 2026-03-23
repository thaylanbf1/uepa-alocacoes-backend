import uvicorn

if __name__ == "__main__":
	app = "app.main:app"
	uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)