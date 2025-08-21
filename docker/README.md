# Docker Development Environment

This directory contains Docker configuration for running Temporal.io server locally for workflow server development.

## Quick Start

1. **Start Temporal services:**
   ```bash
   docker-compose up -d
   ```

2. **Verify services are running:**
   ```bash
   docker-compose ps
   ```

3. **Access Temporal Web UI:**
   Open http://localhost:8080 in your browser

4. **Stop services:**
   ```bash
   docker-compose down
   ```

## Services

### Temporal Server
- **Port:** 7233 (Frontend service)
- **gRPC Port:** 8233
- **Health Check:** `temporal workflow list` (requires Temporal CLI)

### Temporal Web UI
- **Port:** 8088 (http://localhost:8088)
- **Alternative Port:** 8080 (built-in UI from temporal service)
- View workflows, activities, and execution history

### PostgreSQL Database
- **Port:** 5432
- **Database:** temporal, temporal_visibility
- **User:** temporal
- **Password:** temporal

### Elasticsearch (Optional)
- **Port:** 9200
- **Profile:** elasticsearch
- **Usage:** `docker-compose --profile elasticsearch up -d`
- **Purpose:** Advanced visibility features

## Workflow Server Integration

The AroMCP workflow server connects to Temporal using these settings:

```python
# Default configuration
TEMPORAL_HOST = "localhost:7233"
TEMPORAL_NAMESPACE = "default"
TEMPORAL_TASK_QUEUE = "mcp-workflows"
```

## Development Workflow

1. **Start Temporal:**
   ```bash
   docker-compose up -d temporal postgresql
   ```

2. **Run workflow server:**
   ```bash
   ./scripts/run-server.sh workflow
   ```

3. **Test workflow execution:**
   ```bash
   # Using MCP tools
   echo '{"workflow": "test.yaml"}' | workflow_start
   ```

4. **Monitor in Web UI:**
   - Open http://localhost:8088
   - View running workflows
   - Check execution history

## Troubleshooting

### Temporal not ready
- Wait 30-60 seconds after `docker-compose up`
- Check logs: `docker-compose logs temporal`
- Verify PostgreSQL is ready: `docker-compose logs postgresql`

### Connection refused
- Ensure port 7233 is not in use: `lsof -i :7233`
- Check Docker network: `docker network ls`
- Restart services: `docker-compose restart temporal`

### Database issues
- Reset data: `docker-compose down -v`
- Check PostgreSQL logs: `docker-compose logs postgresql`
- Manual database check: `docker-compose exec postgresql psql -U temporal`

## Data Persistence

- **PostgreSQL data:** `postgresql-data` volume
- **Temporal config:** `temporal-data` volume
- **Remove all data:** `docker-compose down -v`

## Production Considerations

For production deployment:

1. **Use external PostgreSQL** with proper backup
2. **Enable authentication** and TLS
3. **Configure resource limits**
4. **Set up monitoring** with Prometheus/Grafana
5. **Enable Elasticsearch** for advanced visibility
6. **Configure archival** for completed workflows

## CLI Tools

Install Temporal CLI for debugging:

```bash
# Install Temporal CLI
curl -sSf https://temporal.download/cli.sh | sh

# List workflows
temporal workflow list

# Show workflow details
temporal workflow show --workflow-id your-workflow-id

# Query workflow
temporal workflow query --workflow-id your-workflow-id --type workflowState
```