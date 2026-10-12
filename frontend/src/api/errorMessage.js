const publicMessage = (value) => {
  if (typeof value === 'string') {
    return value.trim();
  }

  if (Array.isArray(value)) {
    return value
      .map((item) => publicMessage(item))
      .filter(Boolean)
      .join('; ');
  }

  if (value && typeof value === 'object') {
    if (typeof value.msg === 'string' && value.msg.trim()) {
      return value.msg.trim();
    }
    if (typeof value.message === 'string' && value.message.trim()) {
      return value.message.trim();
    }
  }

  return '';
};

export function getErrorMessage(error, fallback = 'Failed to submit.') {
  const responseData = error?.response?.data;
  const detailMessage = publicMessage(responseData?.detail);
  if (detailMessage) return detailMessage;

  const responseMessage = publicMessage(responseData?.message);
  if (responseMessage) return responseMessage;

  const errorMessage = publicMessage(error?.message);
  if (errorMessage) return errorMessage;

  const directMessage = publicMessage(error);
  if (directMessage) return directMessage;

  const safeFallback = publicMessage(fallback);
  return safeFallback || 'Failed to submit.';
}

export default getErrorMessage;
