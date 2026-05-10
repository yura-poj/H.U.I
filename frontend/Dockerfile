FROM node:25-alpine AS deps

WORKDIR /app

COPY package*.json ./
RUN npm install

FROM deps AS dev

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host=0.0.0.0", "--port=5173"]

FROM deps AS build

ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}

COPY . .
RUN npm run build
