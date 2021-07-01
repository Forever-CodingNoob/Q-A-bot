@echo off
ECHO Running deploy commands...

SET PROJECT_ID=qa-study-bot
SET IMAGE_NAME=bot
SET SERVICE_NAME=%IMAGE_NAME%

CMD /c gcloud builds submit --tag gcr.io/%PROJECT_ID%/%IMAGE_NAME%
REM CMD /c gcloud run deploy --image gcr.io/%PROJECT_ID%/%IMAGE_NAME%:latest --platform managed --region=asia-east1 --allow-unauthenticated
CMD /c gcloud run services update %SERVICE_NAME% --image gcr.io/%PROJECT_ID%/%IMAGE_NAME%:latest --platform=managed --region=asia-east1
REM CMD /c gcloud run services add-iam-policy-binding %SERVICE_NAME% --platform=managed --region=asia-east1 --member="allUsers" --role="roles/run.invoker"

ECHO succeeded!