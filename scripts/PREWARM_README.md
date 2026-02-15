# Pre-warming Script

The `prewarm.sh` script prepares your deployment by pulling Docker images and downloading model weights before the first production job is submitted. This significantly reduces the wait time for initial jobs.

## Quick Start

```bash
# After deployment, run:
./deploy.sh prewarm

# Or run directly:
./scripts/prewarm.sh
```

## What It Does

1. **Pulls/builds Docker images** for all model runners:
   - `brineylab/boltz2:latest` (~5 GB)
   - `brineylab/chai1:latest` (~5 GB)
   - `brineylab/ligandmpnn:latest` (~2 GB)
   - Main web application image

2. **Downloads model weights** by running minimal test predictions:
   - Boltz-2 weights (~2-3 GB) → cached to `BOLTZ_CACHE_DIR`
   - Chai-1 weights (~2-3 GB) → cached to `CHAI_CACHE_DIR`
   - LigandMPNN weights (already in Docker image)

3. **Verifies** that containers can run and access GPUs

## When to Run

- **After initial deployment** - Download all weights once
- **After model updates** - New model versions (e.g., Boltz-3)
- **After adding new models** - New model types entirely
- **Before production cutover** - Ensure everything is ready
- **Periodically** - Keep weights up to date

## Usage

### Basic Usage

```bash
./deploy.sh prewarm
```

### With Docker Registry

If you're pulling images from a registry instead of building locally:

```bash
./scripts/prewarm.sh --registry registry.example.com:5000
```

This will pull:
- `registry.example.com:5000/brineylab/boltz2:latest`
- `registry.example.com:5000/brineylab/chai1:latest`
- `registry.example.com:5000/brineylab/ligandmpnn:latest`

### Partial Pre-warming

Skip images if already built/pulled:

```bash
./scripts/prewarm.sh --skip-images
```

Skip weights if already downloaded:

```bash
./scripts/prewarm.sh --skip-weights
```

Only pull/build images (no weight downloads):

```bash
./scripts/prewarm.sh --skip-weights
```

## Requirements

- Docker with GPU support (`nvidia-docker2`)
- NVIDIA GPU accessible to Docker
- Sufficient disk space (~15-20 GB for images + weights)
- Network connectivity for downloads

## Environment Variables

The script reads from `.env` (or `env.example` if `.env` doesn't exist):

```bash
BOLTZ_IMAGE=brineylab/boltz2:latest
BOLTZ_CACHE_DIR=/path/to/boltz_cache

CHAI_IMAGE=brineylab/chai1:latest
CHAI_CACHE_DIR=/path/to/chai_cache

LIGANDMPNN_IMAGE=brineylab/ligandmpnn:latest
```

## Troubleshooting

### GPU not accessible

```
WARNING: GPU not accessible via Docker. Model weight downloads may fail.
```

**Solution**: Install and configure `nvidia-docker2`:

```bash
# Ubuntu/Debian
sudo apt-get install nvidia-docker2
sudo systemctl restart docker

# Test GPU access
docker run --rm --gpus all nvidia/cuda:12.2.2-base-ubuntu22.04 nvidia-smi
```

### Image pull fails

```
WARNING: Failed to pull brineylab/boltz2:latest from registry.
```

**Expected behavior**: If images haven't been pushed to a registry yet, the script will automatically fall back to building them locally.

**Solution for production**:
1. Build images: `docker build -t registry.example.com/boltz2:latest containers/boltz2/`
2. Push to registry: `docker push registry.example.com/boltz2:latest`
3. Run prewarm with registry: `./scripts/prewarm.sh --registry registry.example.com`

### Weight download fails

```
WARNING: Boltz-2 pre-warm failed. Weights may not be fully cached.
```

**Possible causes**:
- Network timeout during download
- Insufficient disk space
- GPU out of memory

**Solution**:
1. Check disk space: `df -h`
2. Check GPU availability: `nvidia-smi`
3. Check network connectivity
4. Re-run: `./scripts/prewarm.sh --skip-images` (skip image pull, retry weights)

### Cache directory permissions

**Solution**: Ensure cache directories are writable. Replace `$DATA_DIR` with your configured data directory (defaults to `./data`):

```bash
sudo chown -R $(whoami):$(whoami) $DATA_DIR/jobs/boltz_cache $DATA_DIR/jobs/chai_cache
```

## Performance Impact

### Time Estimates

| Step | Duration | Network-dependent |
|------|----------|-------------------|
| Image pull/build | 5-15 min | Yes (if pulling) |
| Boltz-2 weights | 5-15 min | Yes |
| Chai-1 weights | 5-15 min | Yes |
| **Total** | **15-45 min** | Yes |

### Disk Usage

| Component | Size |
|-----------|------|
| Boltz-2 image | ~5 GB |
| Chai-1 image | ~5 GB |
| LigandMPNN image | ~2 GB |
| Boltz-2 weights | ~2-3 GB |
| Chai-1 weights | ~2-3 GB |
| **Total** | **~16-20 GB** |

## Benefits

Without pre-warming, the first job for each model will:
1. Pull the Docker image (5-15 min)
2. Download model weights (5-15 min)
3. Run the prediction

**First job total**: 10-30+ minutes

With pre-warming:
- All images are cached locally
- All weights are cached locally

**First job total**: <1-5 minutes (just prediction time)

## Integration with deploy.sh

The prewarm script is integrated into `deploy.sh`:

```bash
# Via deploy.sh (recommended)
./deploy.sh prewarm [options]

# Direct invocation
./scripts/prewarm.sh [options]
```

Both approaches are equivalent. Use whichever is more convenient.

## Example Deployment Workflow

```bash
# 1. Initial setup
./deploy.sh install

# 2. Pre-warm (can run in background)
./deploy.sh prewarm &

# 3. Deploy is ready when prewarm completes
# First jobs will be fast!
```

## See Also

- `deploy.sh` - Main deployment script
- `backup.sh` - Backup script
- `restore.sh` - Restore script
- `env.example` - Environment variable template
