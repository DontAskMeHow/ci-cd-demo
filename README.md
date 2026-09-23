# ci-cd-demo

Демо полного цикла CI/CD простого веб-приложения (Python-backend + nginx)
на GitLab CI: сборка Docker-образов → тесты в docker:dind → публикация
версионных образов в реестр → деплой Ansible-плейбуками через
ansible-control-контейнер → авто-релиз.

## Пайплайн

```mermaid
flowchart TD
    Start([Push в любую ветку]) --> Build

    subgraph Stage_Build [Stage: build]
        Build[build job<br/><b>manual</b><br/>Сборка образов backend/nginx<br/>Сохранение .tar + IMAGE_TAG.txt]
    end

    Build --> Test

    subgraph Stage_Test [Stage: test]
        Test[test job<br/><b>автоматически</b><br/>Загружает образы из артефактов<br/>docker compose up<br/>Запускает test.py]
    end

    Build --> PublishCondition{Ветка = main?}

    PublishCondition -->|нет| EndSkip([publish не запускается])
    PublishCondition -->|да| PublishManual[publish job<br/><b>manual trigger</b><br/>Требует переменные:<br/>BACKEND_VERSION,<br/>NGINX_VERSION,<br/>RELEASE_TAG]

    subgraph Stage_Publish [Stage: publish]
        PublishManual --> ValidateVars{Переменные заданы?}
        ValidateVars -->|нет| FailPublish[❌ Ошибка: переменные обязательны]
        ValidateVars -->|да| DockerLogin[Логин в реестр образов]
        DockerLogin --> BuildVersioned[Сборка образов с версиями<br/>backend:$BACKEND_VERSION<br/>nginx:$NGINX_VERSION]
        BuildVersioned --> TagLatest{Ветка main?}
        TagLatest -->|да| TagLatestImages[Добавить тег latest]
        TagLatest -->|нет| PushImages
        TagLatestImages --> PushImages[Push образов в реестр]
        PushImages --> GenDotenv[Создать release-versions.env<br/>с BACKEND_VERSION, NGINX_VERSION, RELEASE_TAG]
        GenDotenv --> SaveDotenvArtifact[Сохранить как dotenv-артефакт]
    end

    SaveDotenvArtifact --> AutoRelease

    subgraph Stage_Release [Stage: release]
        AutoRelease[auto_release job<br/><b>автоматически</b><br/>После успешного publish] --> CheckReleaseConfig{Существует ли<br/>releases/$RELEASE_TAG.yml<br/>в текущем коммите?}
        CheckReleaseConfig -->|нет| FailRelease[❌ Ошибка: конфиг не найден<br/>Создайте вручную]
        CheckReleaseConfig -->|да| GitSetup[Настройка git user и remote<br/>с CI_JOB_TOKEN]
        GitSetup --> DeleteOldTag[Удалить старый тег $RELEASE_TAG<br/>локально и на origin]
        DeleteOldTag --> CreateTag[Создать аннотированный тег<br/>на CI_COMMIT_SHA]
        CreateTag --> PushTag[push --force]
        PushTag --> ReleaseCLI[release-cli create<br/>с описанием и ссылкой на конфиг]
        ReleaseCLI --> Success([✅ Релиз создан])
    end

    FailPublish --> EndJob([Job failed])
    FailRelease --> EndJob

    style Build fill:none,stroke:#333
    style Test fill:none,stroke:#333
    style PublishManual fill:none,stroke:#333
    style AutoRelease fill:none,stroke:#333
    style ValidateVars fill:none,stroke:#f66
    style CheckReleaseConfig fill:none,stroke:#f66
    style Success fill:none,stroke:#0a0
    style FailPublish fill:none,stroke:#f00
    style FailRelease fill:none,stroke:#f00
```

## Структура

| Путь | Назначение |
| --- | --- |
| `.gitlab-ci.yml` | корневой оркестратор: ci-триггер (main/теги), cd-триггер (только теги) |
| `.gitlab-ci-ci.yml` | стадии build → test → publish → release |
| `.gitlab-ci-cd.yml` | стадия deploy: плейбуки через контейнер ansible-control |
| `backend/`, `nginx/` | Dockerfile + код приложения |
| `docker-compose.yml` | локальная связка nginx + backend |
| `playbooks/` | Ansible-плейбуки деплоя (backend / nginx / all) |
| `inventory/hosts.ini` | инвентарь: группы host'ов и параметры подключения |
| `releases/` | конфиги версий релизов `vX.Y.Z.yml` |
| `templates/` | reusable-компоненты CI (components) |
| `test.py` | проверки эндпоинта (все поля или точечно `--test <поле>`) |

## Переменные CI

`NEXUS_REGISTRY`, `NEXUS_USER`, `NEXUS_PASSWORD`, `GITLAB_TOKEN`;
при запуске publish вручную (Run with variables): `BACKEND_VERSION`,
`NGINX_VERSION`, `RELEASE_TAG`.

## Локальный запуск

```bash
docker compose up -d
python test.py
```

## Лицензия

MIT — см. [LICENSE](LICENSE).
