FROM python:3.11-slim

WORKDIR /app

# Установка Tesseract OCR + зависимости
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-rus \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# pypi.org иногда отвечает медленно
ENV PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=10

# ⚡ Форсируем сброс кэша при изменении этой строки
# v3 — обновление 2026-10-11
ARG CACHE_BUST=3

COPY requirements.txt .

# Очищаем BOM и невидимые символы
RUN sed -i 's/^\xEF\xBB\xBF//' requirements.txt 2>/dev/null || true && \
    sed -i 's/^\xFF\xFE//' requirements.txt 2>/dev/null || true && \
    sed -i 's/^\xFE\xFF//' requirements.txt 2>/dev/null || true && \
    tr -d '\r\0' < requirements.txt > requirements.txt.tmp && mv requirements.txt.tmp requirements.txt 2>/dev/null || true

# Показываем содержимое
RUN echo "=== СОДЕРЖИМОЕ requirements.txt ===" && \
    cat requirements.txt && \
    echo "=== КОНЕЦ ==="

# Устанавливаем все зависимости
RUN set -e && \
    pip_install_retry() { \
        pkg="$1"; attempt=1; \
        while [ "$attempt" -le 3 ]; do \
            if pip install --no-cache-dir --upgrade "$pkg"; then return 0; fi; \
            echo "WARNING: pip install failed for $pkg (attempt $attempt/3), retry in 10s..."; \
            attempt=$((attempt + 1)); \
            [ "$attempt" -le 3 ] && sleep 10; \
        done; \
        return 1; \
    } && \
    echo '=== УСТАНОВКА ЗАВИСИМОСТЕЙ ===' && \
    if [ ! -f requirements.txt ] || [ ! -s requirements.txt ]; then \
        echo 'ERROR: requirements.txt пуст или не существует'; \
        exit 1; \
    else \
        while IFS= read -r line || [ -n "$line" ]; do \
            [ -z "$line" ] && continue; \
            line=$(echo "$line" | sed 's/^\xEF\xBB\xBF//' | sed 's/^\xFF\xFE//' | sed 's/^\xFE\xFF//' | tr -d '\r\0' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'); \
            [ -z "$line" ] && continue; \
            case "$line" in \
              \#*) echo "Комментарий: $line"; continue ;; \
            esac; \
            echo "=== Устанавливаем: $line ===" && \
            if ! pip_install_retry "$line"; then \
                echo "ERROR: Не удалось установить $line" && exit 1; \
            else \
                echo "✅ Успешно установлен: $line"; \
            fi; \
        done < requirements.txt; \
    fi && \
    echo '=== ПРОВЕРКА УСТАНОВЛЕННЫХ ПАКЕТОВ ===' && \
    pip list 2>/dev/null | grep -iE '(telegram|requests|groq|cohere|openai|pytesseract|pillow)' || echo 'WARNING: Некоторые модули не найдены'

# Проверяем что все ключевые модули импортируются
RUN python -c 'import telegram; print("✅ telegram OK")' || (echo 'ERROR: telegram не установлен' && exit 1)
RUN python -c 'import requests; print("✅ requests OK")' || (echo 'ERROR: requests не установлен' && exit 1)
RUN python -c 'import openai; print("✅ openai OK")' || (echo 'ERROR: openai не установлен' && exit 1)
RUN python -c 'import groq; print("✅ groq OK")' || (echo 'ERROR: groq не установлен' && exit 1)
RUN python -c 'import cohere; print("✅ cohere OK")' || (echo 'ERROR: cohere не установлен' && exit 1)
RUN python -c 'import pytesseract; print("✅ pytesseract OK")' || (echo 'ERROR: pytesseract не установлен' && exit 1)
RUN python -c 'from PIL import Image; print("✅ PIL OK")' || (echo 'ERROR: pillow не установлен' && exit 1)

# Проверяем Tesseract
RUN tesseract --version | head -3 && echo '✅ Tesseract OCR установлен'

RUN pip cache purge || true

# Копируем код
COPY . .

ENV DATA_DIR=/app/data
RUN mkdir -p /app/data && chmod 777 /app/data
RUN chown -R $(id -u):$(id -g) /app/data 2>/dev/null || chown -R 1000:1000 /app/data || true

CMD ["python", "bot.py"]
