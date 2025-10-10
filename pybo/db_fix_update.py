# migrations/versions/9ad1cd80ac31_.py
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '9ad1cd80ac31'
down_revision = 'fb07886d9bbb'
branch_labels = None
depends_on = None

def upgrade():
    # 기존에 _alembic_tmp_* 테이블을 직접 DROP/RENAME 하던 코드를 모두 제거
    # 여기서는 버전만 전진(No-Op) 시킨다.
    pass

def downgrade():
    # 상응되게 No-Op
    pass
