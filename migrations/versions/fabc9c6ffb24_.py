"""empty message

Revision ID: fabc9c6ffb24
Revises: 42d7452d27c4
Create Date: 2025-01-15 09:19:17.794474

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fabc9c6ffb24'
down_revision = '42d7452d27c4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('YoutubeURL',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('star_name', sa.String(length=100), nullable=False),
    sa.Column('type_video', sa.String(length=100), nullable=False),
    sa.Column('json_file', sa.String(length=200), nullable=False),
    sa.Column('url', sa.String(length=200), nullable=False),
    sa.Column('summary', sa.String(length=500), nullable=False),
    sa.Column('update_date', sa.String(length=150), nullable=False),
    sa.Column('view_count', sa.String(length=100), nullable=True),
    sa.Column('favorite_count', sa.String(length=100), nullable=True),
    sa.Column('create_date', sa.DateTime(), nullable=False),
    sa.Column('modify_date', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_YoutubeURL'))
    )
    op.drop_table('theme_code')
    op.drop_table('observe_min_data')
    op.drop_table('observe_stock')
    op.drop_table('rank_trade')
    op.drop_table('chartinfo')
    op.drop_table('stockinfo')
    op.drop_table('stocks_for_auto_trade')
    op.drop_table('daily_trade')
    op.drop_table('token_temp')
    op.drop_table('observe_stock_from_vb')
    op.drop_table('daily_data_from_vb')
    op.drop_table('stock_balance_lists')
    op.drop_table('stock_list_from_vb')
    op.drop_table('stockinfo_temp')
    op.drop_table('stock_list_from_k_investor')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('stock_list_from_k_investor',
    sa.Column('no', sa.INTEGER(), nullable=False),
    sa.Column('stockcode', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stockstdcode', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stockname', sa.VARCHAR(length=150), nullable=False),
    sa.Column('cate_large', sa.VARCHAR(length=150), nullable=False),
    sa.Column('cate_medium', sa.VARCHAR(length=150), nullable=False),
    sa.Column('cate_small', sa.VARCHAR(length=150), nullable=False),
    sa.Column('x1_stock', sa.VARCHAR(length=150), nullable=False),
    sa.Column('x2_stock', sa.VARCHAR(length=150), nullable=False),
    sa.Column('x3_stock', sa.VARCHAR(length=150), nullable=False),
    sa.Column('warning_stock', sa.VARCHAR(length=150), nullable=False),
    sa.Column('pre_warning_stock', sa.VARCHAR(length=150), nullable=False),
    sa.Column('x4_stock', sa.VARCHAR(length=150), nullable=False),
    sa.Column('backdoor_listing', sa.VARCHAR(length=150), nullable=False),
    sa.Column('facevalue', sa.VARCHAR(length=150), nullable=False),
    sa.Column('listingdate', sa.VARCHAR(length=150), nullable=False),
    sa.Column('listingvolume', sa.VARCHAR(length=150), nullable=False),
    sa.Column('capital', sa.VARCHAR(length=150), nullable=False),
    sa.Column('closingmonth', sa.VARCHAR(length=150), nullable=False),
    sa.Column('pre_stock', sa.VARCHAR(length=150), nullable=False),
    sa.Column('category', sa.VARCHAR(length=150), nullable=False),
    sa.Column('sales', sa.VARCHAR(length=150), nullable=False),
    sa.Column('sales_profit', sa.VARCHAR(length=150), nullable=False),
    sa.Column('ordinary_profit', sa.VARCHAR(length=150), nullable=False),
    sa.Column('profit', sa.VARCHAR(length=150), nullable=False),
    sa.Column('roe', sa.VARCHAR(length=150), nullable=False),
    sa.Column('basedyear', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stock_amount', sa.VARCHAR(length=150), nullable=False),
    sa.PrimaryKeyConstraint('no', name='pk_stock_list_from_k_investor'),
    sa.UniqueConstraint('stockcode', name='uq_stock_list_from_k_investor_stockcode'),
    sa.UniqueConstraint('stockstdcode', name='uq_stock_list_from_k_investor_stockstdcode')
    )
    op.create_table('stockinfo_temp',
    sa.Column('no', sa.INTEGER(), nullable=False),
    sa.Column('stockcode', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stockname', sa.VARCHAR(length=150), nullable=False),
    sa.Column('currentvalue', sa.VARCHAR(length=150), nullable=False),
    sa.Column('highvalue', sa.VARCHAR(length=150), nullable=False),
    sa.Column('lowvalue', sa.VARCHAR(length=150), nullable=False),
    sa.Column('beginvalue', sa.VARCHAR(length=150), nullable=False),
    sa.Column('diffrate', sa.VARCHAR(length=150), nullable=False),
    sa.Column('diffval', sa.VARCHAR(length=150), nullable=False),
    sa.Column('tradeval', sa.VARCHAR(length=150), nullable=False),
    sa.Column('pre_tradeval', sa.VARCHAR(length=150), nullable=False),
    sa.Column('tvol_vsprevious', sa.VARCHAR(length=150), nullable=False),
    sa.Column('faceval', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stockvol', sa.VARCHAR(length=150), nullable=False),
    sa.Column('capital', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stocksum', sa.VARCHAR(length=150), nullable=False),
    sa.Column('per', sa.VARCHAR(length=150), nullable=False),
    sa.Column('eps', sa.VARCHAR(length=150), nullable=False),
    sa.Column('pbr', sa.VARCHAR(length=150), nullable=False),
    sa.Column('debtrate', sa.VARCHAR(length=150), nullable=False),
    sa.PrimaryKeyConstraint('no', name='pk_stockinfo_temp'),
    sa.UniqueConstraint('stockcode', name='uq_stockinfo_temp_stockcode')
    )
    op.create_table('stock_list_from_vb',
    sa.Column('no', sa.INTEGER(), nullable=False),
    sa.Column('stockcode', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stockname', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stockdate', sa.VARCHAR(length=150), nullable=False),
    sa.Column('method_1', sa.VARCHAR(length=150), nullable=False),
    sa.Column('method_2', sa.VARCHAR(length=150), nullable=False),
    sa.Column('currentvalue', sa.VARCHAR(length=150), nullable=False),
    sa.Column('d5d20', sa.VARCHAR(length=150), nullable=False),
    sa.Column('close5d', sa.VARCHAR(length=150), nullable=False),
    sa.Column('close20d', sa.VARCHAR(length=150), nullable=False),
    sa.Column('closebegin', sa.VARCHAR(length=150), nullable=False),
    sa.Column('closepreclose', sa.VARCHAR(length=150), nullable=False),
    sa.Column('closelow', sa.VARCHAR(length=150), nullable=False),
    sa.Column('highclose', sa.VARCHAR(length=150), nullable=False),
    sa.Column('begin_1', sa.VARCHAR(length=150), nullable=True),
    sa.Column('begin_2', sa.VARCHAR(length=150), nullable=True),
    sa.Column('begin_3', sa.VARCHAR(length=150), nullable=True),
    sa.Column('begin_4', sa.VARCHAR(length=150), nullable=True),
    sa.Column('begin_5', sa.VARCHAR(length=150), nullable=True),
    sa.Column('high_1', sa.VARCHAR(length=150), nullable=True),
    sa.Column('high_2', sa.VARCHAR(length=150), nullable=True),
    sa.Column('high_3', sa.VARCHAR(length=150), nullable=True),
    sa.Column('high_4', sa.VARCHAR(length=150), nullable=True),
    sa.Column('high_5', sa.VARCHAR(length=150), nullable=True),
    sa.Column('first_low_date', sa.VARCHAR(length=150), nullable=True),
    sa.Column('first_low_value', sa.VARCHAR(length=150), nullable=True),
    sa.Column('first_high_date', sa.VARCHAR(length=150), nullable=True),
    sa.Column('first_high_value', sa.VARCHAR(length=150), nullable=True),
    sa.Column('secend_low_date', sa.VARCHAR(length=150), nullable=True),
    sa.Column('secend_low_value', sa.VARCHAR(length=150), nullable=True),
    sa.Column('secend_high_date', sa.VARCHAR(length=150), nullable=True),
    sa.Column('secend_high_value', sa.VARCHAR(length=150), nullable=True),
    sa.Column('high_begin_4', sa.VARCHAR(length=150), nullable=True),
    sa.Column('high_begin_3', sa.VARCHAR(length=150), nullable=True),
    sa.Column('high_begin_2', sa.VARCHAR(length=150), nullable=True),
    sa.Column('high_begin_1', sa.VARCHAR(length=150), nullable=True),
    sa.Column('tradevol_4', sa.VARCHAR(length=150), nullable=True),
    sa.Column('tradevol_3', sa.VARCHAR(length=150), nullable=True),
    sa.Column('tradevol_2', sa.VARCHAR(length=150), nullable=True),
    sa.Column('tradevol_1', sa.VARCHAR(length=150), nullable=True),
    sa.Column('tradevol_0', sa.VARCHAR(length=150), nullable=True),
    sa.Column('d60_d20', sa.VARCHAR(length=150), nullable=True),
    sa.Column('d20_d5', sa.VARCHAR(length=150), nullable=True),
    sa.Column('close_close4', sa.VARCHAR(length=150), nullable=True),
    sa.PrimaryKeyConstraint('no', name='pk_stock_list_from_vb')
    )
    op.create_table('stock_balance_lists',
    sa.Column('no', sa.INTEGER(), nullable=False),
    sa.Column('category', sa.VARCHAR(length=150), nullable=True),
    sa.Column('stockcode', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stockname', sa.VARCHAR(length=150), nullable=False),
    sa.Column('currvalue', sa.VARCHAR(length=150), nullable=True),
    sa.Column('beginvalue', sa.VARCHAR(length=150), nullable=True),
    sa.Column('highvalue', sa.VARCHAR(length=150), nullable=True),
    sa.Column('lowvalue', sa.VARCHAR(length=150), nullable=True),
    sa.Column('tradeval', sa.VARCHAR(length=150), nullable=True),
    sa.Column('tradevalrate', sa.VARCHAR(length=150), nullable=True),
    sa.Column('diffval', sa.VARCHAR(length=150), nullable=True),
    sa.Column('diffrate', sa.VARCHAR(length=150), nullable=True),
    sa.Column('caution', sa.VARCHAR(length=150), nullable=True),
    sa.Column('warning', sa.VARCHAR(length=150), nullable=True),
    sa.Column('remainderqty', sa.VARCHAR(length=150), nullable=False),
    sa.Column('buyprice', sa.VARCHAR(length=150), nullable=False),
    sa.Column('buyamount', sa.VARCHAR(length=150), nullable=False),
    sa.Column('currentvalue', sa.VARCHAR(length=150), nullable=False),
    sa.Column('evalprice', sa.VARCHAR(length=150), nullable=False),
    sa.Column('evalrate', sa.VARCHAR(length=150), nullable=False),
    sa.Column('evalpriceamount', sa.VARCHAR(length=150), nullable=False),
    sa.Column('method_1', sa.VARCHAR(length=150), nullable=False),
    sa.Column('method_2', sa.VARCHAR(length=150), nullable=False),
    sa.Column('buy_previous', sa.VARCHAR(length=150), nullable=True),
    sa.Column('sell_previous', sa.VARCHAR(length=150), nullable=True),
    sa.Column('buy_today', sa.VARCHAR(length=150), nullable=True),
    sa.Column('sell_today', sa.VARCHAR(length=150), nullable=True),
    sa.Column('orderno', sa.VARCHAR(length=150), nullable=True),
    sa.Column('initqty', sa.VARCHAR(length=150), nullable=True),
    sa.Column('remainqty', sa.VARCHAR(length=150), nullable=True),
    sa.Column('buyqty', sa.VARCHAR(length=150), nullable=True),
    sa.PrimaryKeyConstraint('no', name='pk_stock_balance_lists'),
    sa.UniqueConstraint('stockcode', name='uq_stock_balance_lists_stockcode')
    )
    op.create_table('daily_data_from_vb',
    sa.Column('no', sa.INTEGER(), nullable=False),
    sa.Column('stockcode', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stockname', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stockdate', sa.VARCHAR(length=150), nullable=False),
    sa.Column('fromvb', sa.VARCHAR(length=150), nullable=True),
    sa.Column('selecteddate', sa.VARCHAR(length=150), nullable=True),
    sa.Column('selected1', sa.VARCHAR(length=150), nullable=False),
    sa.Column('selected2', sa.VARCHAR(length=150), nullable=False),
    sa.Column('selected3', sa.VARCHAR(length=150), nullable=True),
    sa.Column('selected4', sa.VARCHAR(length=150), nullable=True),
    sa.PrimaryKeyConstraint('no', name='pk_daily_data_from_vb')
    )
    op.create_table('observe_stock_from_vb',
    sa.Column('no', sa.INTEGER(), nullable=False),
    sa.Column('category', sa.VARCHAR(length=150), nullable=True),
    sa.Column('stockcode', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stockname', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stockdate', sa.VARCHAR(length=150), nullable=True),
    sa.Column('method_1', sa.VARCHAR(length=150), nullable=False),
    sa.Column('method_2', sa.VARCHAR(length=150), nullable=False),
    sa.Column('selected1', sa.VARCHAR(length=150), nullable=True),
    sa.Column('selected2', sa.VARCHAR(length=150), nullable=True),
    sa.Column('selected3', sa.VARCHAR(length=150), nullable=True),
    sa.Column('selected4', sa.VARCHAR(length=150), nullable=True),
    sa.Column('selecteddate', sa.VARCHAR(length=150), nullable=True),
    sa.Column('buydate', sa.VARCHAR(length=150), nullable=True),
    sa.Column('tradetime', sa.VARCHAR(length=150), nullable=True),
    sa.Column('currentvalue', sa.VARCHAR(length=150), nullable=True),
    sa.Column('beginvalue', sa.VARCHAR(length=150), nullable=True),
    sa.Column('highvalue', sa.VARCHAR(length=150), nullable=True),
    sa.Column('lowvalue', sa.VARCHAR(length=150), nullable=True),
    sa.Column('cellprice', sa.VARCHAR(length=150), nullable=True),
    sa.Column('buyprice', sa.VARCHAR(length=150), nullable=True),
    sa.Column('tradeval', sa.VARCHAR(length=150), nullable=True),
    sa.Column('tradevalrate', sa.VARCHAR(length=150), nullable=True),
    sa.Column('diffrate', sa.VARCHAR(length=150), nullable=True),
    sa.Column('diffval', sa.VARCHAR(length=150), nullable=True),
    sa.Column('caution', sa.VARCHAR(length=150), nullable=True),
    sa.Column('warning', sa.VARCHAR(length=150), nullable=True),
    sa.Column('orderno', sa.VARCHAR(length=150), nullable=True),
    sa.Column('initqty', sa.VARCHAR(length=150), nullable=True),
    sa.Column('remainqty', sa.VARCHAR(length=150), nullable=True),
    sa.Column('buyqty', sa.VARCHAR(length=150), nullable=True),
    sa.PrimaryKeyConstraint('no', name='pk_observe_stock_from_vb'),
    sa.UniqueConstraint('stockcode', name='uq_observe_stock_from_vb_stockcode')
    )
    op.create_table('token_temp',
    sa.Column('no', sa.INTEGER(), nullable=False),
    sa.Column('approval_key', sa.VARCHAR(length=300), nullable=False),
    sa.Column('token_key', sa.VARCHAR(length=500), nullable=False),
    sa.Column('token_expire', sa.VARCHAR(length=200), nullable=False),
    sa.Column('approval_key_mock', sa.VARCHAR(length=300), nullable=False),
    sa.Column('token_key_mock', sa.VARCHAR(length=500), nullable=False),
    sa.Column('token_expire_mock', sa.VARCHAR(length=200), nullable=False),
    sa.PrimaryKeyConstraint('no', name='pk_token_temp')
    )
    op.create_table('daily_trade',
    sa.Column('no', sa.INTEGER(), nullable=False),
    sa.Column('stockcode', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stockname', sa.VARCHAR(length=150), nullable=False),
    sa.Column('tradedate', sa.VARCHAR(length=150), nullable=False),
    sa.Column('orderno', sa.VARCHAR(length=150), nullable=False),
    sa.Column('orderno_origin', sa.VARCHAR(length=150), nullable=False),
    sa.Column('trade', sa.VARCHAR(length=150), nullable=False),
    sa.Column('trade_name', sa.VARCHAR(length=150), nullable=False),
    sa.Column('orderqty', sa.VARCHAR(length=150), nullable=False),
    sa.Column('orderprice', sa.VARCHAR(length=150), nullable=False),
    sa.Column('ordertime', sa.VARCHAR(length=150), nullable=False),
    sa.Column('total_trade_qty', sa.VARCHAR(length=150), nullable=False),
    sa.Column('avg_price', sa.VARCHAR(length=150), nullable=False),
    sa.Column('total_trade_amount', sa.VARCHAR(length=150), nullable=False),
    sa.Column('order_code', sa.VARCHAR(length=150), nullable=False),
    sa.Column('remain_qty', sa.VARCHAR(length=150), nullable=False),
    sa.Column('trade_condition', sa.VARCHAR(length=150), nullable=False),
    sa.Column('market', sa.VARCHAR(length=150), nullable=False),
    sa.Column('amount_order', sa.VARCHAR(length=150), nullable=False),
    sa.Column('amount_trade_qty', sa.VARCHAR(length=150), nullable=False),
    sa.Column('avg_buy_cost', sa.VARCHAR(length=150), nullable=False),
    sa.Column('amount_cost', sa.VARCHAR(length=150), nullable=False),
    sa.Column('exp_tax', sa.VARCHAR(length=150), nullable=False),
    sa.PrimaryKeyConstraint('no', name='pk_daily_trade')
    )
    op.create_table('stocks_for_auto_trade',
    sa.Column('no', sa.INTEGER(), nullable=False),
    sa.Column('stockcode', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stockname', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stockdate', sa.VARCHAR(length=150), nullable=True),
    sa.Column('method_1', sa.VARCHAR(length=150), nullable=False),
    sa.Column('method_2', sa.VARCHAR(length=150), nullable=False),
    sa.Column('selected1', sa.VARCHAR(length=150), nullable=True),
    sa.Column('selected2', sa.VARCHAR(length=150), nullable=True),
    sa.Column('selected3', sa.VARCHAR(length=150), nullable=True),
    sa.Column('selected4', sa.VARCHAR(length=150), nullable=True),
    sa.Column('selecteddate', sa.VARCHAR(length=150), nullable=True),
    sa.Column('buydate', sa.VARCHAR(length=150), nullable=True),
    sa.Column('tradetime', sa.VARCHAR(length=150), nullable=True),
    sa.Column('currentvalue', sa.VARCHAR(length=150), nullable=True),
    sa.Column('beginvalue', sa.VARCHAR(length=150), nullable=True),
    sa.Column('highvalue', sa.VARCHAR(length=150), nullable=True),
    sa.Column('lowvalue', sa.VARCHAR(length=150), nullable=True),
    sa.Column('cellprice', sa.VARCHAR(length=150), nullable=True),
    sa.Column('buyprice', sa.VARCHAR(length=150), nullable=False),
    sa.Column('tradeval', sa.VARCHAR(length=150), nullable=True),
    sa.Column('tradevalrate', sa.VARCHAR(length=150), nullable=True),
    sa.Column('diffrate', sa.VARCHAR(length=150), nullable=True),
    sa.Column('diffval', sa.VARCHAR(length=150), nullable=True),
    sa.Column('caution', sa.VARCHAR(length=150), nullable=True),
    sa.Column('warning', sa.VARCHAR(length=150), nullable=True),
    sa.Column('orderno', sa.VARCHAR(length=150), nullable=True),
    sa.Column('initqty', sa.VARCHAR(length=150), nullable=True),
    sa.Column('remainqty', sa.VARCHAR(length=150), nullable=True),
    sa.Column('buyqty', sa.VARCHAR(length=150), nullable=True),
    sa.Column('remainderqty', sa.VARCHAR(length=150), nullable=False),
    sa.Column('buyamount', sa.VARCHAR(length=150), nullable=False),
    sa.Column('evalprice', sa.VARCHAR(length=150), nullable=False),
    sa.Column('evalrate', sa.VARCHAR(length=150), nullable=False),
    sa.Column('evalpriceamount', sa.VARCHAR(length=150), nullable=False),
    sa.PrimaryKeyConstraint('no', name='pk_stocks_for_auto_trade'),
    sa.UniqueConstraint('stockcode', name='uq_stocks_for_auto_trade_stockcode')
    )
    op.create_table('stockinfo',
    sa.Column('no', sa.INTEGER(), nullable=False),
    sa.Column('stockcode', sa.VARCHAR(length=150), nullable=False),
    sa.Column('category', sa.VARCHAR(length=2), nullable=False),
    sa.Column('secondcode', sa.VARCHAR(length=200), nullable=False),
    sa.Column('stockname', sa.VARCHAR(length=150), nullable=False),
    sa.Column('currentvalue', sa.VARCHAR(length=150), nullable=False),
    sa.Column('create_date', sa.DATETIME(), nullable=False),
    sa.Column('modify_date', sa.DATETIME(), nullable=False),
    sa.PrimaryKeyConstraint('no', name='pk_stockinfo'),
    sa.UniqueConstraint('stockcode', name='uq_stockinfo_stockcode')
    )
    op.create_table('chartinfo',
    sa.Column('no', sa.INTEGER(), nullable=False),
    sa.Column('stockcode', sa.VARCHAR(length=150), nullable=False),
    sa.Column('date', sa.VARCHAR(length=50), nullable=False),
    sa.Column('beginval', sa.VARCHAR(length=200), nullable=False),
    sa.Column('highval', sa.VARCHAR(length=150), nullable=False),
    sa.Column('lowval', sa.VARCHAR(length=150), nullable=False),
    sa.Column('endval', sa.VARCHAR(length=150), nullable=False),
    sa.Column('tradeval', sa.VARCHAR(length=150), nullable=False),
    sa.Column('tradevol', sa.VARCHAR(length=150), nullable=False),
    sa.Column('changeval', sa.VARCHAR(length=150), nullable=False),
    sa.Column('changesign', sa.VARCHAR(length=2), nullable=False),
    sa.Column('changevol', sa.VARCHAR(length=150), nullable=False),
    sa.PrimaryKeyConstraint('no', name='pk_chartinfo')
    )
    op.create_table('rank_trade',
    sa.Column('no', sa.INTEGER(), nullable=False),
    sa.Column('stockcode', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stockname', sa.VARCHAR(length=150), nullable=False),
    sa.Column('rank', sa.VARCHAR(length=150), nullable=False),
    sa.Column('currentvalue', sa.VARCHAR(length=150), nullable=False),
    sa.Column('tradeval', sa.VARCHAR(length=150), nullable=False),
    sa.Column('sign', sa.VARCHAR(length=150), nullable=False),
    sa.Column('diffrate', sa.VARCHAR(length=150), nullable=False),
    sa.Column('diffval', sa.VARCHAR(length=150), nullable=False),
    sa.Column('pre_tradeval', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stockvol', sa.VARCHAR(length=150), nullable=False),
    sa.Column('avg_vol', sa.VARCHAR(length=150), nullable=False),
    sa.Column('nday_prpr_rate', sa.VARCHAR(length=150), nullable=False),
    sa.Column('vol_incr', sa.VARCHAR(length=150), nullable=False),
    sa.Column('vol_tnrt', sa.VARCHAR(length=150), nullable=False),
    sa.Column('nday_vol_tnrt', sa.VARCHAR(length=150), nullable=False),
    sa.Column('avg_tr_pbmn', sa.VARCHAR(length=150), nullable=False),
    sa.Column('tr_pbmn_tnrt', sa.VARCHAR(length=150), nullable=False),
    sa.Column('nday_tr_pbmn_tnrt', sa.VARCHAR(length=150), nullable=False),
    sa.Column('acml_tr_pbmn', sa.VARCHAR(length=150), nullable=False),
    sa.Column('in_buy_list', sa.VARCHAR(length=150), nullable=False),
    sa.Column('in_observe_list', sa.VARCHAR(length=150), nullable=False),
    sa.Column('method_1', sa.VARCHAR(length=150), nullable=False),
    sa.Column('method_2', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stockdate', sa.VARCHAR(length=150), nullable=False),
    sa.Column('selected_1', sa.VARCHAR(length=150), nullable=False),
    sa.Column('selected_2', sa.VARCHAR(length=150), nullable=False),
    sa.Column('selected_3', sa.VARCHAR(length=150), nullable=False),
    sa.Column('selected_4', sa.VARCHAR(length=150), nullable=False),
    sa.Column('selecteddate', sa.VARCHAR(length=150), nullable=False),
    sa.PrimaryKeyConstraint('no', name='pk_rank_trade')
    )
    op.create_table('observe_stock',
    sa.Column('no', sa.INTEGER(), nullable=False),
    sa.Column('stockcode', sa.VARCHAR(length=150), nullable=False),
    sa.Column('category', sa.VARCHAR(length=2), nullable=False),
    sa.Column('secondcode', sa.VARCHAR(length=200), nullable=False),
    sa.Column('stockname', sa.VARCHAR(length=150), nullable=False),
    sa.Column('currentvalue', sa.VARCHAR(length=150), nullable=False),
    sa.Column('beginvalue', sa.VARCHAR(length=150), nullable=False),
    sa.Column('highvalue', sa.VARCHAR(length=150), nullable=False),
    sa.Column('lowvalue', sa.VARCHAR(length=150), nullable=False),
    sa.Column('tradeval', sa.VARCHAR(length=150), nullable=False),
    sa.Column('diffrate', sa.VARCHAR(length=150), nullable=False),
    sa.Column('diffval', sa.VARCHAR(length=150), nullable=False),
    sa.Column('targetvalue', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stockstatus', sa.VARCHAR(length=150), nullable=False),
    sa.Column('create_date', sa.DATETIME(), nullable=False),
    sa.Column('modify_date', sa.DATETIME(), nullable=False),
    sa.PrimaryKeyConstraint('no', name='pk_observe_stock'),
    sa.UniqueConstraint('stockcode', name='uq_observe_stock_stockcode')
    )
    op.create_table('observe_min_data',
    sa.Column('no', sa.INTEGER(), nullable=False),
    sa.Column('stockcode', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stockname', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stockdate', sa.VARCHAR(length=150), nullable=False),
    sa.Column('method_1', sa.VARCHAR(length=150), nullable=False),
    sa.Column('method_2', sa.VARCHAR(length=150), nullable=False),
    sa.Column('tradetime', sa.VARCHAR(length=150), nullable=True),
    sa.Column('currentvalue', sa.VARCHAR(length=150), nullable=True),
    sa.Column('beginvalue', sa.VARCHAR(length=150), nullable=True),
    sa.Column('highvalue', sa.VARCHAR(length=150), nullable=True),
    sa.Column('lowvalue', sa.VARCHAR(length=150), nullable=True),
    sa.Column('cellprice', sa.VARCHAR(length=150), nullable=True),
    sa.Column('buyprice', sa.VARCHAR(length=150), nullable=True),
    sa.Column('tradeval', sa.VARCHAR(length=150), nullable=True),
    sa.Column('diffrate', sa.VARCHAR(length=150), nullable=True),
    sa.Column('diffval', sa.VARCHAR(length=150), nullable=True),
    sa.PrimaryKeyConstraint('no', name='pk_observe_min_data'),
    sa.UniqueConstraint('stockcode', name='uq_observe_min_data_stockcode')
    )
    op.create_table('theme_code',
    sa.Column('no', sa.INTEGER(), nullable=False),
    sa.Column('themecode', sa.VARCHAR(length=150), nullable=False),
    sa.Column('themename', sa.VARCHAR(length=150), nullable=False),
    sa.Column('stockcode', sa.VARCHAR(length=150), nullable=False),
    sa.PrimaryKeyConstraint('no', name='pk_theme_code')
    )
    op.drop_table('YoutubeURL')
    # ### end Alembic commands ###
