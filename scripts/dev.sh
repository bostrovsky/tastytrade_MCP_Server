#!/bin/bash
# Development environment helper script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to wait for PostgreSQL
wait_for_postgres() {
    echo "Waiting for PostgreSQL to be ready..."
    for i in {1..30}; do
        if docker exec tastytrade-mcp-postgres pg_isready -U tastytrade -d tastytrade_mcp >/dev/null 2>&1; then
            print_status "PostgreSQL is ready!"
            return 0
        fi
        echo -n "."
        sleep 1
    done
    print_error "PostgreSQL did not become ready in time"
    return 1
}

# Function to wait for Redis
wait_for_redis() {
    echo "Waiting for Redis to be ready..."
    for i in {1..30}; do
        if docker exec tastytrade-mcp-redis redis-cli ping >/dev/null 2>&1; then
            print_status "Redis is ready!"
            return 0
        fi
        echo -n "."
        sleep 1
    done
    print_error "Redis did not become ready in time"
    return 1
}

# Main script
main() {
    case "$1" in
        start)
            echo "🚀 Starting development environment..."
            
            # Check for Docker
            if ! command_exists docker; then
                print_error "Docker is not installed. Please install Docker first."
                exit 1
            fi
            
            # Start Docker services
            print_status "Starting Docker services..."
            docker compose up -d
            
            # Wait for services
            wait_for_postgres
            wait_for_redis
            
            # Run database migrations (if needed)
            if [ -d "migrations" ]; then
                print_status "Running database migrations..."
                export PATH="$HOME/.local/bin:$PATH"
                poetry run alembic upgrade head || print_warning "Migrations may have already been applied"
            fi
            
            echo ""
            print_status "Development environment is ready!"
            echo ""
            echo "Services running:"
            echo "  • PostgreSQL: localhost:5432"
            echo "  • Redis: localhost:6379"
            echo ""
            echo "Optional tools (run with --profile tools):"
            echo "  • PgAdmin: http://localhost:5050"
            echo "  • RedisInsight: http://localhost:5540"
            echo ""
            echo "Run './scripts/dev.sh seed' to seed the database"
            echo "Run './scripts/dev.sh stop' to stop all services"
            ;;
            
        stop)
            echo "🛑 Stopping development environment..."
            docker compose down
            print_status "All services stopped"
            ;;
            
        restart)
            $0 stop
            $0 start
            ;;
            
        seed)
            echo "🌱 Seeding database..."
            
            # Check if services are running
            if ! docker ps | grep -q tastytrade-mcp-postgres; then
                print_warning "PostgreSQL is not running. Starting services..."
                $0 start
            fi
            
            # Run seed script
            export PATH="$HOME/.local/bin:$PATH"
            poetry run python scripts/seed_dev_data.py "$2"
            ;;
            
        reset)
            echo "🔄 Resetting database..."
            export PATH="$HOME/.local/bin:$PATH"
            poetry run python scripts/seed_dev_data.py --reset
            ;;
            
        logs)
            echo "📜 Showing logs..."
            docker compose logs -f "$2"
            ;;
            
        status)
            echo "📊 Environment status:"
            echo ""
            docker compose ps
            ;;
            
        tools)
            echo "🔧 Starting development tools..."
            docker compose --profile tools up -d
            print_status "Development tools started:"
            echo "  • PgAdmin: http://localhost:5050 (admin@tastytrade.local / admin)"
            echo "  • RedisInsight: http://localhost:5540"
            ;;
            
        clean)
            echo "🧹 Cleaning up..."
            docker compose down -v
            print_status "All services stopped and volumes removed"
            ;;
            
        *)
            echo "TastyTrade MCP Development Environment Helper"
            echo ""
            echo "Usage: $0 {start|stop|restart|seed|reset|logs|status|tools|clean}"
            echo ""
            echo "Commands:"
            echo "  start    - Start all development services"
            echo "  stop     - Stop all services"
            echo "  restart  - Restart all services"
            echo "  seed     - Seed database with test data"
            echo "  reset    - Reset and reseed database"
            echo "  logs     - Show service logs (optional: service name)"
            echo "  status   - Show status of all services"
            echo "  tools    - Start development tools (PgAdmin, RedisInsight)"
            echo "  clean    - Stop services and remove all data"
            exit 1
            ;;
    esac
}

main "$@"