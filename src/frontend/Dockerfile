# Stage 1: Build React app
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --production=false

# Copy source code
COPY . .

# Set build-time environment variable for API URL (will be overridden at runtime)
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL:-http://localhost:8000}

# Build app (outputs to 'build' directory as per vite.config.ts)
RUN npm run build

# Stage 2: Production with Nginx
FROM nginx:alpine

# Copy built files from 'build' directory (not 'dist')
COPY --from=builder /app/build /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
