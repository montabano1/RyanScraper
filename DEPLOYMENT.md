# Deployment Guide

## Prerequisites
1. Install the DigitalOcean CLI (doctl):
```bash
brew install doctl
```

2. Create a DigitalOcean account at https://cloud.digitalocean.com

3. Create an API token:
   - Go to API > Generate New Token
   - Give it a name (e.g., "ryan-scraper")
   - Copy the token

## Deployment Steps

1. Authenticate with DigitalOcean:
```bash
doctl auth init
# Paste your API token when prompted
```

2. Create a new app:
```bash
doctl apps create --spec .do/app.yaml
```

3. Add environment variables:
   - Go to your app's settings in the DigitalOcean dashboard
   - Add the following environment variables:
     - `SUPABASE_URL`
     - `SUPABASE_KEY`

4. Enable automatic deployments:
   - Go to your app's settings
   - Connect your GitHub repository
   - Enable "Automatically deploy changes"

## Monitoring and Logs

1. View logs:
```bash
doctl apps logs $APP_ID
```

2. Monitor app status:
```bash
doctl apps list
```

## Updating the App

1. Push changes to GitHub:
```bash
git add .
git commit -m "your commit message"
git push origin main
```

2. DigitalOcean will automatically deploy the changes

## Troubleshooting

1. If the app fails to build:
   - Check the build logs: `doctl apps logs $APP_ID --type build`
   - Verify Dockerfile configuration
   - Check environment variables

2. If scraping is slow:
   - Monitor CPU/Memory usage in DigitalOcean dashboard
   - Consider upgrading to a larger instance size
   - Check the Chrome flags in the scraper configuration

3. If the app crashes:
   - Check runtime logs: `doctl apps logs $APP_ID --type run`
   - Verify Gunicorn configuration
   - Check memory usage

## Cost Management

- Current plan (Professional-xs): $12/month
- Monitor usage in DigitalOcean dashboard
- Set up billing alerts
- Consider scheduling downtimes for non-business hours
