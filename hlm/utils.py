from scipy import sparse as spar
import numpy as np
from numpy import linalg as nla
from scipy.sparse import linalg as spla
import scipy.linalg as scla
from warnings import warn as Warn

__all__ = ['grid_det']
PUBLIC_DICT_ATTS = [k for k in dir(dict) if not k.startswith('_')]

def grid_det(W, parmin=None, parmax=None, parstep=None, grid=None):
    """
    This is a utility function to set up the grid of matrix determinants over a
    range of spatial parameters for a given W. 
    """
    if (parmin is None) and (parmax is None):
        parmin, parmax = speigen_range(W)
    if parstep is None:
        parstep = (parmax - parmin) / 1000
    if grid is None:
        grid = np.arange(parmin, parmax, parstep)
    logdets = [splogdet(speye_like(W) - rho * W) for rho in grid]
    grid = np.vstack((grid, np.array(logdets).reshape(grid.shape)))
    return grid

####################
# MATRIX UTILITIES #
####################

def splogdet(matrix):
    """
    compute the log determinant via an appropriate method. 
    """
    redo = False
    if spar.issparse(matrix):
        LU = spla.splu(matrix)
        ldet = np.sum(np.log(np.abs(LU.U.diagonal())))
    else:
        sgn, ldet = nla.slogdet(matrix)
        if np.isinf(ldet) or sgn is 0:
            Warn('Dense log determinant via numpy.linalg.slogdet() failed!')
            redo = True
        if sgn not in [-1,1]:
            Warn("Drastic loss of precision in numpy.linalg.slogdet()!")
            redo = True
        ldet = sgn*ldet
    if redo:
        Warn("Please pass convert to a sparse weights matrix. Trying sparse determinant...", UserWarning)
        ldet = splogdet(spar.csc_matrix(matrix))
    return ldet

def speye(i, sparse=True):
    """
    constructs a square identity matrix according to i, either sparse or dense
    """
    if sparse:
        return spar.identity(i)
    else:
        return np.identity(i)

spidentity = speye

def speye_like(matrix):
    """
    constructs an identity matrix depending on the input dimension and type
    """
    if matrix.shape[0] != matrix.shape[1]:
        raise UserWarning("Matrix is not square")
    else:
        return speye(matrix.shape[0], sparse=spar.issparse(matrix))

spidentity_like = speye_like

def speigen_range(matrix, retry=True, coerce=True):
    """
    Construct the eigenrange of a potentially sparse matrix. 
    """
    if spar.issparse(matrix):
        try:
            emax = spla.eigs(matrix, k=1, which='LR')[0]
        except (spla.ArpackNoConvergence, spla.ArpackError) as e:
            rowsums = np.unique(np.asarray(matrix.sum(axis=1)).flatten())
            if np.allclose(rowsums, np.ones_like(rowsums)):
                emax = np.array([1])
            else:
                Warn('Maximal eigenvalue computation failed to converge'
                     ' and matrix is not row-standardized.')
                raise e
        emin = spla.eigs(matrix, k=1, which='SR')[0]
        if coerce:
            emax = emax.astype(float)
            emin = emin.astype(float)
    else:
        try:
            eigs = nla.eigvals(matrix)
            emin, emax = eigs.min().astype(float), eigs.max().astype(float)
        except Exception as e:
            Warn('Dense eigenvector computation failed!')
            if retry:
                Warn('Retrying with sparse matrix...')
                spmatrix = spar.csc_matrix(matrix)
                speigen_range(spmatrix)
            else:
                Warn('Bailing...')
                raise e 
    return emin, emax

def spinv(M):
    """
    Compute an inverse of a matrix using the appropriate sparse or dense
    function
    """
    if spar.issparse(M):
        return spla.inv(M)
    else:
        return nla.inv(M)

#########################
# STATISTICAL UTILITIES #
#########################

def chol_mvn(Mu, Sigma):
    """
    Sample from a Multivariate Normal given a mean & Covariance matrix, using
    cholesky decomposition of the covariance

    That is, new values are generated according to :
    New = Mu + cholesky(Sigma) . N(0,1)

    Parameters
    ----------
    Mu      :   np.ndarray (p,1)
                An array containing the means of the multivariate normal being
                sampled
    Sigma   :   np.ndarray (p,p)
                An array containing the covariance between the dimensions of the
                multivariate normal being sampled

    Returns
    -------
    np.ndarray of size (p,1) containing draws from the multivariate normal
    described by MVN(Mu, Sigma)
    """
    D = scla.cholesky(Sigma, overwrite_a = True)
    e = np.random.normal(0,1,size=Mu.shape)
    kernel = np.dot(D.T, e)
    return Mu + kernel

def sma_covariance(param, W):
    # type (float, W) -> np.dnarray
    """
    This computes a covariance matrix for a SMA-type error specification:

    ( (I + param * W)(I + param * W)^T)
    
    this always returns a dense array
    """
    half = speye_like(W) + param * W
    whole = half.dot(half.T)
    return whole.toarray()

def se_covariance(param, W):
    # type (float, W) -> np.dnarray
    """
    This computes a covariance matrix for a SAR-type error specification:

    ( (I - param * W)^T(I - param * W) )^{-1}
    
    and always returns a dense matrix

    """
    half = speye_like(W) - param * W
    to_inv = half.T.dot(half)
    return np.linalg.inv(half.toarray())