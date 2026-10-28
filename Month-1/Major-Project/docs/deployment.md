# Deployment Guide

## Overview

This guide covers deploying the Product Sentiment Analyzer to production using:
- **Backend**: Render (or AWS EC2)
- **Frontend**: Vercel (or Netlify)
- **Database**: MongoDB Atlas

## Prerequisites

- GitHub repository
- MongoDB Atlas account
- Render account
- Vercel/Netlify account

## Database Setup (MongoDB Atlas)

1. Create a new cluster on [MongoDB Atlas](https://cloud.mongodb.com)
2. Choose a cloud provider and region (prefer same region as backend)
3. Create a database user with read/write permissions
4. Whitelist IP addresses (0.0.0.0/0 for all, or specific Render IPs)
5. Get connection string:
   ```
   mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/sentiment_analyzer
   ```

## Backend Deployment (Render)

### Option A: Render Web Service

1. Connect GitHub repository to Render
2. Create new **Web Service**
3. Configure:
   - **Name**: `sentiment-analyzer-api`
   - **Region**: Same as MongoDB
   - **Branch**: `main`
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn run:app`
   - **Instance Type**: Free or Starter

4. Add Environment Variables:
   ```
   MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/sentiment_analyzer
   DATABASE_NAME=sentiment_analyzer
   FLASK_ENV=production
   FRONTEND_URL=https://your-frontend.vercel.app
   SECRET_KEY=generate-secure-random-key
   PORT=10000
   ```

5. Add **Disk** (optional, for Chrome cache):
   - Name: `chrome-cache`
   - Mount Path: `/home/user/.cache`
   - Size: 1 GB

6. Deploy

### Option B: Docker on Render

1. Create new **Web Service** with **Docker**
2. Dockerfile path: `backend/Dockerfile`
3. Same environment variables

### Health Check

Render will check `/api/health` automatically. Ensure it returns 200.

## Frontend Deployment (Vercel)

### Option A: Vercel (Recommended)

1. Import project from GitHub on [Vercel](https://vercel.com)
2. Configure:
   - **Framework Preset**: Vite
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`

3. Add Environment Variables:
   ```
   VITE_API_URL=https://your-backend.onrender.com
   ```

4. Deploy

### Option B: Netlify

1. Connect repository on [Netlify](https://netlify.com)
2. Configure:
   - **Base Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Publish Directory**: `dist`

3. Add Environment Variables (same as Vercel)
4. Add `_redirects` file in `frontend/public/`:
   ```
   /api/*  https://your-backend.onrender.com/api/:splat  200
   /*      /index.html   200
   ```

## CORS Configuration

Update backend `FRONTEND_URL` to match production frontend URL exactly (including protocol).

```python
# In backend/app/config/settings.py
FRONTEND_URL = "https://your-app.vercel.app"  # No trailing slash
```

## Production Build

### Backend
```bash
cd backend
pip install -r requirements.txt
gunicorn run:app --workers 4 --bind 0.0.0.0:10000
```

### Frontend
```bash
cd frontend
npm run build
# Output in dist/
```

## Environment Variables Summary

### Backend (.env)
| Variable | Development | Production |
|----------|-------------|------------|
| MONGODB_URI | mongodb://localhost:27017 | mongodb+srv://... |
| DATABASE_NAME | sentiment_analyzer | sentiment_analyzer |
| FLASK_ENV | development | production |
| FRONTEND_URL | http://localhost:5173 | https://your-app.vercel.app |
| SECRET_KEY | dev-secret | **secure-random-64-chars** |
| PORT | 5000 | 10000 (Render) |

### Frontend (.env)
| Variable | Development | Production |
|----------|-------------|------------|
| VITE_API_URL | http://localhost:5000 | https://your-api.onrender.com |

## SSL/HTTPS

- Render provides automatic HTTPS
- Vercel/Netlify provide automatic HTTPS
- Ensure all API calls use HTTPS in production

## Monitoring

### Render
- Logs: Available in dashboard
- Metrics: CPU, Memory, Requests
- Alerts: Configure for downtime

### MongoDB Atlas
- Metrics: Connections, Operations, Storage
- Alerts: Configure for storage/cpu

## Troubleshooting

### Backend won't start
- Check logs for import errors
- Verify `MONGODB_URI` format
- Ensure Chrome/ChromeDriver installed (for Docker)

### Scraping fails in production
- Render free tier may not have Chrome
- Consider using a scraping API service
- Or upgrade to paid tier with Chrome support

### CORS errors
- Verify `FRONTEND_URL` matches exactly
- Check browser network tab for actual origin

### Database connection fails
- Check IP whitelist in Atlas
- Verify connection string format
- Ensure database user has correct permissions

## CI/CD Pipeline (GitHub Actions)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Render
        uses: render/deploy-action@v1
        with:
          service-id: ${{ secrets.RENDER_SERVICE_ID }}
          api-key: ${{ secrets.RENDER_API_KEY }}

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Vercel
        uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          working-directory: ./frontend
```

## Cost Optimization

- **MongoDB Atlas**: Free tier (M0) - 512MB storage
- **Render**: Free tier - 750 hours/month, spins down after inactivity
- **Vercel**: Free tier - 100GB bandwidth
- **Total**: $0/month for low traffic

For production traffic:
- MongoDB Atlas M10: ~$57/month
- Render Starter: $7/month
- Vercel Pro: $20/month