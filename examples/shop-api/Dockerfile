FROM node:22.23.1-bookworm-slim@sha256:6c74791e557ce11fc957704f6d4fe134a7bc8d6f5ca4403205b2966bd488f6b3
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
COPY examples/shop-api/package.json examples/shop-api/package.json
RUN npm ci --workspace examples/shop-api --include-workspace-root --no-audit --no-fund
COPY examples/shop-api examples/shop-api
RUN npm run build --workspace examples/shop-api
USER node
CMD ["npm", "run", "start", "--workspace", "examples/shop-api"]
