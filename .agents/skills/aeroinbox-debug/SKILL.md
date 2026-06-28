---
name: aeroinbox-debug
description: Diagnostic cheatsheet for debugging AeroInbox microservices running on AKS production cluster. Use when debugging pod issues, meeting banner not showing, service bus errors, or scaling problems.
---

## Prerequisites
- Must SSH into the Bastion Jumpbox VM first (Azure Portal -> Bastion -> vm-jumpbox)
- Namespace for all workloads: `production`
- ArgoCD namespace: `argocd`

## Pod Status & Logs

### Check all pod status
```bash
kubectl get pods -n production
```

### Stream logs for a specific service
```bash
kubectl logs -l app.kubernetes.io/name=meeting-service -n production --tail=200 -f
kubectl logs -l app.kubernetes.io/name=api-service -n production --tail=200 -f
kubectl logs -l app.kubernetes.io/name=gmail-service -n production --tail=200 -f
```

### Search logs for errors or a specific email ID
```bash
kubectl logs -l app.kubernetes.io/name=meeting-service -n production --tail=3000 | grep -i "error\|exception\|fail"
kubectl logs -l app.kubernetes.io/name=api-service -n production --tail=3000 | grep -i "19f0e25e0cee467b"
```

---

## Port-Forward to Query Service APIs Directly

```bash
# Kill any existing port-forwards first
killall kubectl 2>/dev/null || true

# Port-forward meeting-service
kubectl port-forward service/aeroinbox-meeting-service -n production 8000:8000 > pf.log 2>&1 &
sleep 2

# Query pending meetings for a user
curl -s "http://localhost:8000/meetings/pending?user_id=aknagasai2104@gmail.com"

# Manually trigger meeting detection
curl -i -X POST http://localhost:8000/meetings/detect \
  -H "Content-Type: application/json" \
  -d '{"emails": [{"id": "test-id", "account_email": "user@gmail.com", "subject": "Meeting", "sender": "sender@example.com", "body": "Meeting body", "snippet": "snippet"}]}'
```

---

## KEDA Autoscaling

### Check KEDA scaling status and trigger
```bash
kubectl describe scaledobject aeroinbox-meeting-service-scaler -n production
```

### Force scale down meeting-service pods immediately (bypass ArgoCD)
```bash
kubectl patch scaledobject aeroinbox-meeting-service-scaler -n production \
  --type='json' -p='[{"op": "replace", "path": "/spec/maxReplicaCount", "value": 2}]'
```

### Permanently fix KEDA maxReplicas (via Helm values.yaml)
- Edit `aeroinbox-helm/values.yaml` -> `meeting-service.autoscaling.maxReplicas`
- Commit and push to `aeroinbox-helm` repo; ArgoCD will sync within 3 minutes

---

## ArgoCD Sync

### Check sync status
```bash
kubectl get applications -n argocd
```

### Force immediate sync (skip the 3-minute poll)
```bash
kubectl annotate application aeroinbox -n argocd \
  argocd.argoproj.io/refresh=hard --overwrite
```

---

## Meeting Banner Debug (Frontend)

The purple "Add to Calendar" banner renders when:
`selectedEmail.id === meeting.source_email_id` (checked in frontend EmailCard.jsx)

If banner is missing for a known meeting email:
1. Port-forward meeting-service and query `/meetings/pending?user_id=<EMAIL>`
2. Check the `source_email_id` field in the JSON response
3. Compare it with the email ID visible in the URL or browser network tab
4. If they differ, the `_handle_existing_meeting()` fix in `main.py` needs to be redeployed
