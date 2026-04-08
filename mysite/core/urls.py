from django.urls import path

from .fixed_assets_views import FDRatesAPIView, DebtFundsAPIView
#from .mf_views import MF_CagrSummaryAPIView
from .mf_views import FundPredictionsAPIView, MF_CagrSummaryAPIView
from core.ml_views import FundPredictionsAPIView 
from .views import (
    BuildInvestmentRecommendationsView,
    LatestInvestmentRecommendationsView,
    recommendations_list,
)

from django.urls import path
# =====================
# AUTH
# =====================
from .auth_views import (
    login_view,
    register_view,
    profile_view,
    forgot_send_otp,
    forgot_verify_otp,
    forgot_reset_password,
    change_password_view,
)

# =====================
# MODULE VIEWS
# =====================
from .income_views import income_list_create, income_update_delete
from .saving_views import saving_list_create, saving_update_delete
from .emergency_views import emergency_list_create, emergency_update_delete
from .loan_views import loan_list_create, loan_update_delete
from .insurance_views import insurance_list_create, insurance_detail
from .expenses_views import (
    ExpenseListCreateView,
    ExpenseUpdateDeleteView,
    expense_ocr,
    recommendation_list
)

# =====================
# INVESTMENT
# =====================
from .investment_views import (
    InvestmentRecommendAPIView,
    portfolio_summary,
    investment_transactions,
)

urlpatterns = [
    # =====================
    # AUTH
    # =====================
    path("register/", register_view),
    path("login/", login_view),

    path("forgot/send-otp/", forgot_send_otp),
    path("forgot/verify-otp/", forgot_verify_otp),
    path("forgot/reset-password/", forgot_reset_password),

    path("profile/", profile_view),
    path("change-password/", change_password_view),

    # =====================
    # MODULES
    # =====================
    path("income/", income_list_create),
    path("income/<int:pk>/", income_update_delete),

    path("saving/", saving_list_create),
    path("saving/<int:pk>/", saving_update_delete),

    path("emergency/", emergency_list_create),
    path("emergency/<int:pk>/", emergency_update_delete),

    path("loan/", loan_list_create),
    path("loan/<int:pk>/", loan_update_delete),

    path("insurance/", insurance_list_create),
    path("insurance/<int:pk>/", insurance_detail),

    path("expenses/", ExpenseListCreateView.as_view()),
    path("expenses/<int:pk>/", ExpenseUpdateDeleteView.as_view()),
    path("expenses/ocr/", expense_ocr, name="expense-ocr"),
    path("recommendations/", recommendation_list, name="recommendation-list"),

    # =====================
    # INVESTMENT
    # =====================
    path("investment/recommend", InvestmentRecommendAPIView.as_view(), name="investment-recommend"),
    path("investment/mf-cagr-summary/", MF_CagrSummaryAPIView.as_view()),
    path("investment/fixed-assets/fd-rates/", FDRatesAPIView.as_view()),
    path("investment/fixed-assets/debt-funds/", DebtFundsAPIView.as_view()),
    path("investment/portfolio/summary/", portfolio_summary, name="portfolio-summary"),
    path("investment/transactions/", investment_transactions, name="investment-transactions"),
    path("investment/predictions/", FundPredictionsAPIView.as_view(), name="investment-predictions"),
    
    path("recommendations/", recommendations_list),

    path(
        "investment/recommendations/build/",
        BuildInvestmentRecommendationsView.as_view(),
        name="build-investment-recommendations",
    ),
    path(
        "investment/recommendations/latest/",
        LatestInvestmentRecommendationsView.as_view(),
        name="latest-investment-recommendations",
    ),
]