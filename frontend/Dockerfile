FROM node:26-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM nginx:alpine
# O nginx troca ${API_ORIGIN} e ${WS_ORIGIN} pelo ambiente ao subir (templates da imagem oficial).
ENV API_ORIGIN=http://localhost:8000 WS_ORIGIN=ws://localhost:8000
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
