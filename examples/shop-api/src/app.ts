import express from "express";

export const app = express();
app.disable("x-powered-by");
app.get("/healthz", (_request, response) => {
  response.json({ status: "ok", service: "shop-api", phase: 0 });
});
