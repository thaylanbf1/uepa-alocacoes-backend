## AlocacoesUEPA - Backend (FastAPI)

API para gestão de salas e reservas integrada ao Google Calendar.

### Executar com Docker
- Subir: `docker compose up -d`
- Logs do app: `docker compose logs -f app`
- Parar: `docker compose down`
- URL base: `http://localhost:8000`
- Documentação interativa (quando ativa): `http://localhost:8000/docs` e `http://localhost:8000/redoc`

Banco padrão no Docker: MySQL (service `db`). A URL é injetada no container: `mysql+mysqldb://user:password@db:3306/alocacoes`

### Autenticação
- Fluxo: OAuth2 Password (Bearer).
- Obtenha o token em `POST /auth/token` (form-data padrão OAuth2: `username`, `password`).
- Use o token nas rotas protegidas via header: `Authorization: Bearer <token>`.

---

## Rotas

### Health
- GET `/health`
  - Descrição: Verificação de saúde.
  - Auth: Não
  - Response 200:
    ```json
    {"status":"ok"}
    ```

### Auth
- POST `/auth/token`
  - Descrição: Gera token de acesso (Bearer) a partir de credenciais.
  - Auth: Não
  - Body (form `application/x-www-form-urlencoded` - OAuth2PasswordRequestForm):
    - `username`: string (email)
    - `password`: string
  - Responses:
    - 200:
      ```json
      {"access_token":"<jwt>","token_type":"bearer"}
      ```
    - 401: Invalid credentials

### Users
- GET `/users/me`
  - Descrição: Retorna informações do usuário autenticado.
  - Auth: Bearer
  - Responses:
    - 200 (autenticado):
      ```json
      {
        "id": 1,
        "nome": "Fulano",
        "email": "fulano@exemplo.com",
        "tipo_usuario": 1,
        "authenticated": true
      }
      ```
    - 200 (não autenticado, via regra interna): `{"authenticated": false}`

### Rooms
Prefixo: `/rooms`

- GET `/rooms/`
  - Descrição: Lista salas.
  - Auth: Bearer (mínimo role 1)
  - Response 200 (array de salas):
    ```json
    [{
      "id": 10,
      "codigo_sala": 101,
      "tipo_sala": "laboratorio",
      "ativada": true,
      "limite_usuarios": 30,
      "descricao_sala": "Lab 1",
      "imagem": null,
      "sala_ativada": true
    }]
    ```

- POST `/rooms/`
  - Descrição: Cria sala.
  - Auth: Bearer (Admin)
  - Body (application/json):
    ```json
    {
      "codigo_sala": 101,
      "tipo_sala": "laboratorio",
      "ativada": true,
      "limite_usuarios": 30,
      "descricao_sala": "Lab 1",
      "imagem": null
    }
    ```
  - Responses:
    - 201: objeto sala criado
    - 400: `tipo_sala inválido` (se não presente na configuração)

- PUT `/rooms/{room_id}`
  - Descrição: Atualiza uma sala.
  - Auth: Bearer (Admin)
  - Body (application/json, campos parciais aceitos):
    ```json
    {
      "tipo_sala": "auditorio",
      "ativada": false,
      "limite_usuarios": 100,
      "descricao_sala": "Auditório",
      "imagem": "https://...",
      "sala_ativada": true
    }
    ```
  - Responses:
    - 200: objeto sala atualizado
    - 400: `tipo_sala inválido`
    - 404: Room not found

- DELETE `/rooms/{room_id}`
  - Descrição: Remove uma sala (bloqueia se há reservas futuras).
  - Auth: Bearer (Admin)
  - Responses:
    - 204: sem conteúdo
    - 400: possui reservas futuras
    - 404: Room not found

### Reservations
Prefixo: `/reservations`

Observação: As reservas usam integração com Google Calendar. As respostas (create/update/list) retornam a estrutura de evento do Google; list retorna `{"items":[...]}`.

- GET `/reservations/`
  - Descrição: Lista eventos de reserva dentro de um período, com filtros opcionais.
  - Auth: Bearer (mínimo role 1)
  - Query:
    - `date_from` (ISO 8601 UTC, obrigatório)
    - `date_to` (ISO 8601 UTC, obrigatório)
    - `room_id` (opcional)
    - `user_id` (opcional)
  - Responses:
    - 200:
      ```json
      {"items":[{ "...evento_google..." }]}
      ```
    - 400: `date_from and date_to are required` ou `Google credentials not connected`

- POST `/reservations/`
  - Descrição: Cria reserva (evento no Google Calendar).
  - Auth: Bearer (Admin)
  - Body (application/json):
    ```json
    {
      "fk_usuario": 1,
      "fk_sala": 10,
      "tipo": "aula",
      "dia_horario_inicio": "2025-01-10T12:00:00Z",
      "dia_horario_saida": "2025-01-10T14:00:00Z",
      "uso": "Laboratório de POO",
      "justificativa": "Disciplina X",
      "oficio": null
    }
    ```
  - Responses:
    - 201: objeto do evento criado (Google)
    - 400: `End must be after start` ou `Google credentials not connected`
    - 404: Room not found
    - 409: Conflito de horário

- PUT `/reservations/{reservation_id}`
  - Descrição: Atualiza reserva (evento Google). Campos parciais aceitos.
  - Auth: Bearer (Admin)
  - Body (application/json, qualquer subset):
    ```json
    {
      "fk_usuario": 1,
      "fk_sala": 10,
      "tipo": "reuniao",
      "dia_horario_inicio": "2025-01-10T13:00:00Z",
      "dia_horario_saida": "2025-01-10T15:00:00Z",
      "uso": "Reunião",
      "justificativa": "Planejamento",
      "oficio": "123/2025"
    }
    ```
  - Responses:
    - 200: evento atualizado (Google)
    - 400: `Google credentials not connected or update failed` ou validação de horário

- DELETE `/reservations/{reservation_id}`
  - Descrição: Remove reserva (evento Google).
  - Auth: Bearer (Admin)
  - Responses:
    - 204: sem conteúdo
    - 400: `Google credentials not connected or delete failed`

### Calendar
Prefixo: `/calendar`

- GET `/calendar/events`
  - Descrição: Lista eventos do Google Calendar por janela (day|week|month|semester), com filtros.
  - Auth: Bearer (mínimo role 1)
  - Query:
    - `view` (default `month`, um de: `day|week|month|semester`)
    - `anchor` (ISO 8601 UTC, opcional; centro da janela)
    - `room_id` (opcional)
    - `user_id` (opcional)
  - Responses:
    - 200: `{"items":[...eventos_google...]}`
    - 400: `Google credentials not connected`

- GET `/calendar/google/events`
  - Descrição: Lista eventos do Google no intervalo explícito.
  - Auth: Bearer (mínimo role 1)
  - Query:
    - `start` (ISO 8601 UTC, obrigatório)
    - `end` (ISO 8601 UTC, obrigatório)
    - `calendar_id` (opcional)
  - Responses:
    - 200: `{"items":[...eventos_google...]}`
    - 400: `Google credentials not connected`

- POST `/calendar/google/events`
  - Descrição: Cria evento no Google Calendar.
  - Auth: Bearer (mínimo role 1)
  - Body:
    ```json
    {
      "summary": "Título",
      "description": "Opcional",
      "start_dt_utc": "2025-01-10T12:00:00Z",
      "end_dt_utc": "2025-01-10T13:00:00Z",
      "location": "Sala 10",
      "calendar_id": null
    }
    ```
  - Responses:
    - 201: evento criado (Google)
    - 400: `Google credentials not connected`

- PATCH `/calendar/google/events/{event_id}`
  - Descrição: Atualiza parcialmente um evento do Google.
  - Auth: Bearer (mínimo role 1)
  - Body (quaisquer campos):
    ```json
    {
      "summary": "Novo título",
      "description": "Nova desc",
      "start_dt_utc": "2025-01-10T13:00:00Z",
      "end_dt_utc": "2025-01-10T14:00:00Z",
      "location": "Sala 11",
      "calendar_id": null
    }
    ```
  - Responses:
    - 200: evento atualizado (Google)
    - 400: `Google credentials not connected or update failed`

- DELETE `/calendar/google/events/{event_id}`
  - Descrição: Remove evento do Google Calendar.
  - Auth: Bearer (mínimo role 1)
  - Query:
    - `calendar_id` (opcional)
  - Responses:
    - 204: sem conteúdo
    - 400: `Google credentials not connected or delete failed`

### Google OAuth (credenciais)
Prefixo: `/google`

- GET `/google/connect`
  - Descrição: Inicia o fluxo OAuth do Google (redireciona para consentimento).
  - Auth: Bearer
  - Pré-requisitos: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` configurados.
  - Response: 302 Redirect

- GET `/google/callback`
  - Descrição: Callback do OAuth do Google; persiste credenciais do usuário.
  - Auth: Bearer
  - Responses:
    - 200: `{"status":"connected"}`
    - 400: `Missing state`

- GET `/google/status`
  - Descrição: Indica se o usuário autenticado possui credenciais Google ativas.
  - Auth: Bearer
  - Response 200:
    ```json
    {"connected": true}
    ```

---

## Esquemas (resumo)

### Room (entrada/saída)
```json
{
  "id": 10,               // (saída)
  "codigo_sala": 101,
  "tipo_sala": "laboratorio",
  "ativada": true,
  "limite_usuarios": 30,
  "descricao_sala": "Lab 1",
  "imagem": null,
  "sala_ativada": true     // (saída)
}
```

### Reservation (entrada)
```json
{
  "fk_usuario": 1,
  "fk_sala": 10,
  "tipo": "aula",
  "dia_horario_inicio": "2025-01-10T12:00:00Z",
  "dia_horario_saida": "2025-01-10T14:00:00Z",
  "uso": "opcional",
  "justificativa": "opcional",
  "oficio": "opcional"
}
```

Notas:
- Datas esperam ISO 8601 em UTC (ex.: `2025-01-10T12:00:00Z`).
- Autorizações por papel: `ROLE_USER` (1), `ROLE_ADMIN` (2), `ROLE_SUPERADMIN` (3). Algumas rotas exigem role mínima.
- Respostas de calendário/reservas retornam payloads do Google Calendar.


