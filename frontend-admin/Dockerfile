FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# Expose Vite port and API port
EXPOSE 5173
EXPOSE 8000

# Start both Vite dev server and API server
CMD ["npm", "run", "dev:all"]
